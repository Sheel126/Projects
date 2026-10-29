"""Phase 4 statistics and the lockbox guard (lesson 04)."""

import math
import subprocess

import numpy as np
import pytest

from liquid_atm_quant.validation import (LockboxRefused, check_preregistration, cscv_pbo,
                                         deflated_sharpe, expected_max_sharpe, open_once,
                                         probabilistic_sharpe, stationary_bootstrap)


def test_expected_max_sharpe_matches_the_paper():
    # For unit variance the expected maximum of N standard normals: ~1.54 for 10, ~3.25 for 1000.
    # It grows with N, scales with sqrt(V), and is 0 for one trial.
    assert expected_max_sharpe(1.0, 1) == 0.0
    small, large = expected_max_sharpe(1.0, 10), expected_max_sharpe(1.0, 1000)
    assert 1.4 < small < 1.7 and 3.0 < large < 3.4
    assert expected_max_sharpe(4.0, 10) == pytest.approx(2 * small)


def test_psr_is_one_half_at_the_benchmark_and_falls_with_fat_tails():
    assert probabilistic_sharpe(0.1, 0.1, 1000, 0.0, 3.0) == pytest.approx(0.5)
    normal = probabilistic_sharpe(0.1, 0.05, 1000, 0.0, 3.0)
    fat = probabilistic_sharpe(0.1, 0.05, 1000, -1.0, 10.0)
    assert 0.5 < fat < normal < 1.0


def test_dsr_penalizes_many_trials():
    rng = np.random.default_rng(0)
    r = rng.normal(0.0008, 0.01, 2000)                       # ~1.27 annual Sharpe
    trials = rng.normal(0.0, 0.03, 50)
    few, many = deflated_sharpe(r, trials, 2), deflated_sharpe(r, trials, 50)
    assert many.dsr < few.dsr
    assert many.expected_max_sharpe > few.expected_max_sharpe


def test_pbo_is_low_when_one_trial_truly_dominates_and_high_for_pure_noise():
    # One draw of noise still has trials that were lucky over the whole sample; it is the average
    # over draws that sits near 1/2.
    names = [f"t{i}" for i in range(10)]
    pbos = [cscv_pbo(np.random.default_rng(s).normal(0, 0.01, (800, 10)), names, blocks=8).pbo
            for s in range(30)]
    assert 0.35 < np.mean(pbos) < 0.65
    noise = np.random.default_rng(1).normal(0, 0.01, (800, 10))
    edge = noise.copy()
    edge[:, 3] += 0.003
    out = cscv_pbo(edge, [f"t{i}" for i in range(10)], blocks=8)
    assert out.pbo < 0.05 and next(iter(out.in_sample_winners)) == "t3"


def test_bootstrap_is_reproducible_and_centred():
    x = np.random.default_rng(2).normal(0.0004, 0.01, 1500)
    a, b = stationary_bootstrap(x, draws=500), stationary_bootstrap(x, draws=500)
    assert a == b
    assert a["ci90"][0] < a["annual_mean"] < a["ci90"][1]
    assert a["annual_mean"] == pytest.approx(x.mean() * 252)


def _repo(tmp_path):
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    for k, v in (("user.email", "t@example.com"), ("user.name", "t")):
        subprocess.run(["git", "config", k, v], cwd=tmp_path, check=True)
    pre = tmp_path / "preregistration.md"
    pre.write_text("rules\n")
    return pre


def test_lockbox_refuses_uncommitted_rules_and_opens_only_once(tmp_path):
    pre = _repo(tmp_path)
    marker = tmp_path / "lockbox_opened.json"
    with pytest.raises(LockboxRefused, match="not committed"):
        check_preregistration(pre)
    subprocess.run(["git", "add", "."], cwd=tmp_path, check=True)
    subprocess.run(["git", "commit", "-qm", "rules"], cwd=tmp_path, check=True)
    pre.write_text("rules, edited after the fact\n")
    with pytest.raises(LockboxRefused, match="uncommitted"):
        open_once(marker, pre, {})
    subprocess.run(["git", "checkout", "-q", "--", pre.name], cwd=tmp_path, check=True)
    record = open_once(marker, pre, {"candidate": "x"})
    assert marker.exists() and len(record["preregistration_commit"]) == 40
    with pytest.raises(LockboxRefused, match="already opened"):
        open_once(marker, pre, {})


def test_sharpe_units_are_per_period():
    r = np.full(252, 0.001) + np.tile([0.01, -0.01], 126)
    d = deflated_sharpe(r, np.array([0.0, 0.05]), 2)
    assert d.sharpe_annual == pytest.approx(d.sharpe * math.sqrt(252))
