"""python -m pytest -q test_pose_map.py   (necesita node para comparar con handpose.js)"""
import json
import pathlib
import random
import shutil
import subprocess
import types

import pytest

from cv.pose_map import PoseMapper

JS = pathlib.Path(__file__).resolve().parents[1] / "viewer3d" / "handpose.js"


def hand(cx, cy, size, pinch):
    """mano sintetica: muneca en (cx, cy+size/2), nudillo medio arriba; pulgar-indice separados 'pinch' veces el ancho de palma."""
    lm = [types.SimpleNamespace(x=cx, y=cy) for _ in range(21)]
    lm[0] = types.SimpleNamespace(x=cx, y=cy + size / 2)
    lm[9] = types.SimpleNamespace(x=cx, y=cy - size / 2)
    lm[5] = types.SimpleNamespace(x=cx - 0.04, y=cy - size / 2)
    lm[17] = types.SimpleNamespace(x=cx + 0.04, y=cy - size / 2)
    lm[13] = types.SimpleNamespace(x=cx + 0.02, y=cy - size / 2)
    lm[4] = types.SimpleNamespace(x=cx, y=cy)
    lm[8] = types.SimpleNamespace(x=cx + 0.08 * pinch, y=cy)
    return lm


def settle(lm):
    m = PoseMapper()
    for _ in range(60):
        p = m.update(lm, 1.0)
    return p


def test_centro_es_reposo_aproximado():
    p = settle(hand(0.5, 0.5, 0.21, 0.55))
    assert abs(p["yaw"]) < 2 and abs(p["th"] - 45) < 10 and p["phi"] == pytest.approx(40)


def test_direcciones():
    assert settle(hand(0.85, 0.5, 0.2, 0.5))["yaw"] < -60          # derecha de la imagen -> yaw negativo
    assert settle(hand(0.5, 0.15, 0.2, 0.5))["th"] > settle(hand(0.5, 0.85, 0.2, 0.5))["th"]
    near, far = settle(hand(0.5, 0.5, 0.30, 0.5)), settle(hand(0.5, 0.5, 0.12, 0.5))
    assert near["psi"] - near["th"] == pytest.approx(-35) and far["psi"] - far["th"] == pytest.approx(-135)
    assert settle(hand(0.5, 0.5, 0.2, 0.2))["phi"] == 0 and settle(hand(0.5, 0.5, 0.2, 0.9))["phi"] == 40


def test_suavizado_no_salta():
    m = PoseMapper()
    y0 = m.update(hand(0.2, 0.5, 0.2, 0.5))["yaw"]
    y1 = m.update(hand(0.8, 0.5, 0.2, 0.5))["yaw"]
    assert y0 > 40 and abs(y1 - y0) < 0.5 * 2 * 90 * 0.6      # no salta de golpe al nuevo valor (alpha 0.35)


@pytest.mark.skipif(shutil.which("node") is None, reason="sin node")
def test_igual_que_el_js():
    random.seed(1)
    cases = [(random.uniform(0, 1), random.uniform(0, 1), random.uniform(0.05, 0.4), random.uniform(0, 1.2)) for _ in range(30)]
    code = """const H=require(%r);const cs=%s;const m=H.create();const out=[];
    for(const [cx,cy,s,p] of cs){const lm=Array.from({length:21},()=>({x:cx,y:cy}));
    lm[0]={x:cx,y:cy+s/2};lm[9]={x:cx,y:cy-s/2};lm[5]={x:cx-0.04,y:cy-s/2};lm[17]={x:cx+0.04,y:cy-s/2};lm[13]={x:cx+0.02,y:cy-s/2};lm[4]={x:cx,y:cy};lm[8]={x:cx+0.08*p,y:cy};
    const r=m.update(lm,{aspect:1.0});out.push([r.yaw,r.th,r.psi,r.phi]);}console.log(JSON.stringify(out));""" % (str(JS), json.dumps(cases))
    js = json.loads(subprocess.check_output(["node", "-e", code]))
    m = PoseMapper()
    for (cx, cy, s, p), j in zip(cases, js):
        r = m.update(hand(cx, cy, s, p), 1.0)
        assert [r["yaw"], r["th"], r["psi"], r["phi"]] == pytest.approx(j, abs=1e-6)
