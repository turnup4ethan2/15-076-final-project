#!/usr/bin/env julia
"""
Robust-style monthly water allocation LP for the Guadalquivir basin.

Reads Python pipeline outputs under `data/processed/`:
  - inflow_forecasts.csv   (quantile storage deltas from lstm_inflow.py)
  - demand_provincial_monthly.csv
  - reservoirs_weekly.csv (last observed volume → initial storage)
  - guadalquivir_reservoirs_seed.csv (reservoir → province incidence)

Decision variables: releases x[r,p,t] (hm³) from reservoir r to province p
in forecast month t, only on seed edges (each major reservoir serves its
listed province — a documented geographic simplification).

Mass balance uses the chosen quantile of *net* storage change as the
exogenous “natural” term (same interpretation as the LSTM training target).
Default quantile is P10 for conservative planning.

Environment:
  LP_SCENARIO   p10 | p50 | p90   (default p10)
  DELTA_SCALE   float multiplier on natural deltas (default 1.0)
  LP_STRESS_LIST  optional comma-separated extra scales, e.g. "1.0,0.85,0.7"
                    — each writes an additional block of rows tagged scenario

Outputs:
  data/processed/lp_allocations.csv
  data/processed/lp_summary.csv
"""

using CSV
using DataFrames
using Dates
using JuMP
using HiGHS

const ROOT = normpath(joinpath(@__DIR__, ".."))
const PROCESSED = joinpath(ROOT, "data", "processed")

_mean(a::AbstractVector{<:Real}) = isempty(a) ? NaN : sum(a) / length(a)

function _median(a::AbstractVector{<:Real})
    b = sort!(collect(a))
    isempty(b) && return NaN
    n = length(b)
    return isodd(n) ? Float64(b[(n + 1) ÷ 2]) : Float64(b[n ÷ 2] + b[n ÷ 2 + 1]) / 2
end

function _read_or_error(path::AbstractString, desc::AbstractString)
    isfile(path) || error("Missing $desc: $path\nRun the Python ingest + lstm + demand pipeline first.")
    CSV.read(path, DataFrame)
end

function scenario_column(q::AbstractString)
    q = lowercase(strip(q))
    q == "p10" && return :p10_storage_delta_hm3
    q == "p50" && return :p50_storage_delta_hm3
    q == "p90" && return :p90_storage_delta_hm3
    error("LP_SCENARIO must be p10, p50, or p90; got $(repr(q))")
end

function latest_volume_by_reservoir(weekly::DataFrame, reservoirs::Vector{String})::Dict{String,Float64}
    rs = Set(reservoirs)
    sub = weekly[in.(weekly.reservoir_name, Ref(rs)), :]
    isempty(sub) && return Dict{String,Float64}()
    d = Dict{String,Float64}()
    for g in groupby(sub, :reservoir_name)
        gg = sort(DataFrame(g), :week_ending)
        res = String(gg.reservoir_name[end])
        v = gg.volume_hm3[end]
        if isfinite(v)
            d[res] = Float64(v)
        end
    end
    return d
end

function build_edges(forecasts::DataFrame, seed::DataFrame)
    fn = unique(forecasts.reservoir_name)
    d = Dict{String,String}()
    for r in eachrow(seed)
        d[String(r.name)] = String(r.province)
    end
    edges = Tuple{String,String}[]
    for res in fn
        res = String(res)
        p = get(d, res, nothing)
        if p !== nothing
            push!(edges, (res, p))
        end
    end
    return edges
end

function demand_matrix(demand::DataFrame, provinces::Vector{String}, months::Vector{Int})
    mat = zeros(Float64, length(provinces), length(months))
    pidx = Dict(p => i for (i, p) in enumerate(provinces))
    for r in eachrow(demand)
        haskey(pidx, r.province) || continue
        mi = findfirst(==(Int(r.month)), months)
        mi === nothing && continue
        mat[pidx[r.province], mi] = Float64(r.demand_hm3)
    end
    return mat
end

function solve_allocation(;
    delta_col::Symbol,
    delta_scale::Float64,
    scenario_name::AbstractString,
)
    fc_path = joinpath(PROCESSED, "inflow_forecasts.csv")
    dm_path = joinpath(PROCESSED, "demand_provincial_monthly.csv")
    wk_path = joinpath(PROCESSED, "reservoirs_weekly.csv")
    sd_path = joinpath(PROCESSED, "guadalquivir_reservoirs_seed.csv")

    forecasts = _read_or_error(fc_path, "inflow forecasts")
    demand = _read_or_error(dm_path, "monthly demand")
    weekly = _read_or_error(wk_path, "weekly reservoir series")
    seed = _read_or_error(sd_path, "reservoir seed list")

    if !hasproperty(forecasts, delta_col)
        error("Forecast file missing column $(String(delta_col))")
    end

    sort!(forecasts, [:reservoir_name, :forecast_month, :horizon_months])
    months = sort(unique(Date.(forecasts.forecast_month)))
    length(months) >= 1 || error("No forecast months in inflow_forecasts.csv")

    edges = build_edges(forecasts, seed)
    isempty(edges) && error(
        "No (reservoir, province) edges after joining forecasts with guadalquivir_reservoirs_seed.csv. " *
        "Check that reservoir_name values match the seed `name` column.",
    )

    served = Set(first.(edges))
    forecasts = forecasts[in.(forecasts.reservoir_name, Ref(served)), :]
    nrow(forecasts) == 0 && error("After joining to seed reservoirs, inflow_forecasts.csv has no rows.")
    reservoirs = sort!(collect(served))
    provinces = sort(unique(last.(edges)))
    R = length(reservoirs)
    P = length(provinces)
    T = length(months)
    r_idx = Dict(r => i for (i, r) in enumerate(reservoirs))
    p_idx = Dict(p => i for (i, p) in enumerate(provinces))

    allowed = falses(R, P)
    for (res, prov) in edges
        haskey(r_idx, res) && haskey(p_idx, prov) || continue
        allowed[r_idx[res], p_idx[prov]] = true
    end

    cap = zeros(R)
    delta = zeros(R, T)
    for g in groupby(forecasts, :reservoir_name)
        res = String(g.reservoir_name[1])
        haskey(r_idx, res) || continue
        ri = r_idx[res]
        cmed = _median(collect(skipmissing(g.capacity_hm3)))
        cap[ri] = isnan(cmed) ? 1e3 : cmed
        sg = sort(g, [:forecast_month, :horizon_months])
        for (ti, m) in enumerate(months)
            rows = subset(sg, :forecast_month => ByRow(d -> Date(d) == m))
            nrow(rows) == 0 && continue
            vals = rows[!, delta_col]
            delta[ri, ti] = Float64(_mean(collect(skipmissing(vals)))) * delta_scale
        end
    end

    vol0 = latest_volume_by_reservoir(weekly, reservoirs)
    S0 = zeros(R)
    for (i, res) in enumerate(reservoirs)
        v = get(vol0, res, nothing)
        if v !== nothing && isfinite(v)
            S0[i] = max(0.0, v)
        else
            S0[i] = 0.5 * max(cap[i], 1.0)
        end
        if isfinite(cap[i]) && cap[i] > 0
            S0[i] = min(S0[i], cap[i])
        end
    end

    month_int = month.(months)
    dem = demand_matrix(demand, provinces, Vector{Int}(month_int))
    total_dem = sum(dem)
    w = total_dem > 0 ? vec(sum(dem, dims=2)) ./ total_dem : ones(P) ./ P

    model = Model(HiGHS.Optimizer)
    set_silent(model)

    @variable(model, S[1:R, 0:T] >= 0)
    @variable(model, x[r=1:R, p=1:P, t=1:T; allowed[r, p]] >= 0)
    @variable(model, deliv[1:P, 1:T] >= 0)

    @constraint(model, [r in 1:R], S[r, 0] == S0[r])
    @constraint(model, [r in 1:R, t in 1:T], S[r, t] <= max(cap[r], 1e-6))

    for r in 1:R, t in 1:T
        rel = sum(x[r, p, t] for p in 1:P if allowed[r, p]; init = 0.0)
        @constraint(model, S[r, t] == S[r, t - 1] + delta[r, t] - rel)
    end

    for p in 1:P, t in 1:T
        inflow_p = sum(x[r, p, t] for r in 1:R if allowed[r, p]; init = 0.0)
        @constraint(model, deliv[p, t] <= dem[p, t])
        @constraint(model, deliv[p, t] <= inflow_p)
    end

    @objective(model, Max, sum(w[p] * deliv[p, t] for p in 1:P, t in 1:T))

    optimize!(model)
    st = termination_status(model)
    st in (JuMP.MOI.OPTIMAL, JuMP.MOI.LOCALLY_SOLVED) || error("Solver failed: $st")

    z = objective_value(model)
    alloc_rows = DataFrame(
        scenario = String[],
        reservoir = String[],
        province = String[],
        forecast_month = Date[],
        horizon_index = Int[],
        release_hm3 = Float64[],
    )
    for r in 1:R, p in 1:P, t in 1:T
        allowed[r, p] || continue
        xv = value(x[r, p, t])
        xv > 1e-9 || continue
        push!(alloc_rows, (scenario_name, reservoirs[r], provinces[p], months[t], t, xv))
    end

    prov_col = [provinces[p] for t in 1:T for p in 1:P]
    month_col = [months[t] for t in 1:T for p in 1:P]
    dem_col = [dem[p, t] for t in 1:T for p in 1:P]
    del_col = [value(deliv[p, t]) for t in 1:T for p in 1:P]
    deliv_df = DataFrame(;
        scenario = fill(scenario_name, P * T),
        province = prov_col,
        forecast_month = month_col,
        demand_hm3 = dem_col,
        delivered_hm3 = del_col,
    )

    shortfall = sum(max(0.0, dem_col[k] - del_col[k]) for k in eachindex(dem_col))
    summary = DataFrame(
        scenario = [scenario_name],
        delta_quantile = [String(delta_col)],
        delta_scale = [delta_scale],
        objective_weighted_deliveries = [z],
        total_demand_hm3 = [sum(dem)],
        total_delivered_hm3 = [sum(deliv_df.delivered_hm3)],
        shortfall_hm3 = [max(0.0, shortfall)],
        n_reservoirs = [R],
        n_provinces = [P],
        n_months = [T],
    )

    return alloc_rows, deliv_df, summary
end

function main()
    q = get(ENV, "LP_SCENARIO", "p10")
    col = scenario_column(q)
    base_scale = parse(Float64, get(ENV, "DELTA_SCALE", "1.0"))
    extra = get(ENV, "LP_STRESS_LIST", "")
    scales = Float64[base_scale]
    if !isempty(strip(extra))
        append!(scales, parse.(Float64, split(extra, ',')))
        unique!(sort!(scales))
    end

    all_alloc = nothing
    all_deliv = nothing
    all_sum = nothing

    for s in scales
        tag = "$(q)_scale$(s)"
        a, d, sm = solve_allocation(; delta_col = col, delta_scale = s, scenario_name = tag)
        if all_alloc === nothing
            all_alloc, all_deliv, all_sum = a, d, sm
        else
            all_alloc = vcat(all_alloc, a; cols = :union)
            all_deliv = vcat(all_deliv, d; cols = :union)
            all_sum = vcat(all_sum, sm; cols = :union)
        end
    end

    mkpath(PROCESSED)
    CSV.write(joinpath(PROCESSED, "lp_allocations.csv"), all_alloc)
    CSV.write(joinpath(PROCESSED, "lp_deliveries.csv"), all_deliv)
    CSV.write(joinpath(PROCESSED, "lp_summary.csv"), all_sum)
    println("Wrote:")
    println("  ", joinpath("data", "processed", "lp_allocations.csv"))
    println("  ", joinpath("data", "processed", "lp_deliveries.csv"))
    println("  ", joinpath("data", "processed", "lp_summary.csv"))
    println()
    println(all_sum)
end

main()
