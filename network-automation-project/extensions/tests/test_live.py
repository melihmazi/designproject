"""Canli ag testleri: validate.py'nin topladigi durumu kontrol grubu basina bir teste donusturur.

    pytest extensions/tests --live
    pytest extensions/tests --live --only MRK-DAG1 MRK-DAG2 --partial
"""
import pytest

pytestmark = pytest.mark.live


def failures(health, prefix):
    return [f"{c['cihaz']} {c['kontrol']}: beklenen {c['beklenen']!r}, gercek {c['gercek']!r}"
            for c in health["kontroller"] if c["kontrol"].startswith(prefix) and c["durum"] == "HATA"]


def count(health, prefix):
    return sum(1 for c in health["kontroller"] if c["kontrol"].startswith(prefix) and c["durum"] == "OK")


def test_tum_cihazlar_erisilebilir(health):
    assert not failures(health, "Erisim")
    assert count(health, "Erisim") == health["ozet"]["cihaz"]


def test_kablolama_cdp(health):
    assert not failures(health, "CDP")


def test_etherchannel(health):
    assert not failures(health, "EtherChannel")


def test_ospf_komsuluklari(health):
    assert not failures(health, "OSPF")
    if not health["kismi"]:
        assert count(health, "OSPF") == 14


def test_hsrp_rolleri(health):
    assert not failures(health, "HSRP")
    if not health["kismi"]:
        assert count(health, "HSRP") == 14


def test_gre_tuneli(health):
    assert not failures(health, "Tunnel")
