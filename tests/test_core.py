import numpy as np
from safeblock.fetch import build_where
from safeblock.analyze import kabco, class_weight, eb

def test_where_escapes():
    assert build_where("O'Town", 2019) == "CrashTownName='O''Town' AND CrashDateYear>=2019"

def test_kabco():
    assert kabco("Fatal Injury (K)") == "K" and kabco("No Apparent Injury (O)") == "O" and kabco(None) == "U"

def test_class_weight():
    assert class_weight(["primary_link", "x"]) == 4 and class_weight("residential") == 1

def test_eb_shrinks_toward_mean():
    rng = np.random.default_rng(0); x = rng.integers(1, 20, 500).astype(float)
    y = rng.poisson(0.5 * x); y[0] = 200
    mu, alpha, ebv, _ = eb(y.astype(float), x)
    assert mu[0] < ebv[0] < y[0]
