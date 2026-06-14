"""
A deliberately small economic-dispatch experiment: classical optimum vs QAOA.

A handful of dispatchable generators, each with a capacity and a commitment
cost, must cover a target load. Choosing the committed subset at minimum cost
while meeting demand is a binary quadratic problem. We encode it as a QUBO,

    cost(x) = sum_i cost_i x_i  +  P * (target - sum_i capacity_i x_i)^2 ,

solve it exactly by enumerating all 2^N commitments, and solve it again with a
compact statevector QAOA, then compare. The QAOA here is a from-scratch
statevector simulation (cost layer diagonal in the computational basis, a
transverse-field mixer, angles optimised classically); it makes no
quantum-advantage claim and is sized so the classical optimum is known. It can
be swapped for a hardware or qiskit backend without changing the interface.
"""
from __future__ import annotations

import numpy as np
from scipy.optimize import minimize

# capacity in 100-MW blocks, cost in $/MWh; 7 units -> 7 qubits
DEFAULT_UNITS = [
    {"name": "Hydro", "capacity": 4.0, "cost": 12.0},
    {"name": "CCGT-1", "capacity": 7.0, "cost": 31.0},
    {"name": "CCGT-2", "capacity": 4.5, "cost": 34.0},
    {"name": "CT-1", "capacity": 5.0, "cost": 42.0},
    {"name": "CT-2", "capacity": 3.0, "cost": 38.0},
    {"name": "Battery", "capacity": 2.5, "cost": 20.0},
    {"name": "Peaker", "capacity": 2.0, "cost": 55.0},
]


def build_qubo(units, target_load, *, penalty=10.0):
    """Return symmetric Q and constant so cost(x) = x^T Q x + const, x in {0,1}^N."""
    n = len(units)
    cap = np.array([u["capacity"] for u in units], dtype="float64")
    cost = np.array([u["cost"] for u in units], dtype="float64")
    Q = np.zeros((n, n))
    for i in range(n):
        Q[i, i] = cost[i] + penalty * (cap[i] ** 2 - 2 * target_load * cap[i])
    for i in range(n):
        for j in range(i + 1, n):
            Q[i, j] = Q[j, i] = penalty * cap[i] * cap[j]
    const = penalty * target_load ** 2
    return Q, const


def _cost_vector(Q, const, n):
    idx = np.arange(2 ** n)
    bits = ((idx[:, None] & (1 << np.arange(n)[::-1])) > 0).astype("float64")
    costs = np.einsum("bi,ij,bj->b", bits, Q, bits) + const
    return costs, bits


def brute_force(Q, const, n):
    costs, bits = _cost_vector(Q, const, n)
    i = int(np.argmin(costs))
    return {"bitstring": bits[i].astype(int).tolist(), "cost": float(costs[i])}


def _apply_mixer(state, beta, n):
    c, s = np.cos(beta), -1j * np.sin(beta)
    gate = np.array([[c, s], [s, c]], dtype="complex128")
    psi = state.reshape([2] * n)
    for k in range(n):
        psi = np.moveaxis(np.tensordot(gate, psi, axes=([1], [k])), 0, k)
    return psi.reshape(-1)


def _expectation(params, costs, n, p):
    gammas, betas = params[:p], params[p:]
    psi = np.full(2 ** n, 1.0 / np.sqrt(2 ** n), dtype="complex128")
    for layer in range(p):
        psi = np.exp(-1j * gammas[layer] * costs) * psi          # diagonal cost layer
        psi = _apply_mixer(psi, betas[layer], n)
    probs = np.abs(psi) ** 2
    return float(np.sum(probs * costs)), probs


def qaoa_solve(Q, const, n, *, p=4, restarts=16, topk=16, seed=0):
    """Optimise QAOA angles from several random starts; return the best commitment.

    The cost energies are normalised before the phase separator so the angles
    sweep meaningful phases (the optimum is invariant under affine scaling), and
    the lowest-cost state among the most probable measurements is returned.
    """
    costs, bits = _cost_vector(Q, const, n)
    norm = (costs - costs.mean()) / (costs.std() + 1e-9)
    rng = np.random.default_rng(seed)
    best = None
    for _ in range(restarts):
        x0 = rng.uniform(0, np.pi, 2 * p)
        res = minimize(lambda pr: _expectation(pr, norm, n, p)[0], x0,
                       method="COBYLA", options={"maxiter": 300})
        if best is None or res.fun < best.fun:
            best = res
    _, probs = _expectation(best.x, norm, n, p)
    cand = np.argsort(probs)[::-1][:min(topk, 2 ** n)]
    pick = int(cand[np.argmin(costs[cand])])
    return {"bitstring": bits[pick].astype(int).tolist(), "cost": float(costs[pick]),
            "prob_of_solution": float(probs[pick]), "p": p}


def dispatch_experiment(units=None, target_load=None, *, penalty=10.0, p=3, seed=0):
    """Run the classical and QAOA solvers on one dispatch instance and compare."""
    units = units or DEFAULT_UNITS
    n = len(units)
    if target_load is None:
        target_load = round(0.55 * sum(u["capacity"] for u in units), 2)
    Q, const = build_qubo(units, target_load, penalty=penalty)
    exact = brute_force(Q, const, n)
    qaoa = qaoa_solve(Q, const, n, p=p, seed=seed)

    def served(bitstring):
        return round(sum(u["capacity"] for u, b in zip(units, bitstring) if b), 2)

    def dollars(bitstring):
        return round(sum(u["cost"] for u, b in zip(units, bitstring) if b), 2)

    return {
        "n_units": n, "target_load": target_load, "penalty": penalty,
        "exact": {**exact, "committed": [u["name"] for u, b in zip(units, exact["bitstring"]) if b],
                  "served_capacity": served(exact["bitstring"]), "commit_cost": dollars(exact["bitstring"])},
        "qaoa": {**qaoa, "committed": [u["name"] for u, b in zip(units, qaoa["bitstring"]) if b],
                 "served_capacity": served(qaoa["bitstring"]), "commit_cost": dollars(qaoa["bitstring"])},
        "optimum_recovered": bool(qaoa["bitstring"] == exact["bitstring"]
                                  or abs(qaoa["cost"] - exact["cost"]) < 1e-6),
    }
