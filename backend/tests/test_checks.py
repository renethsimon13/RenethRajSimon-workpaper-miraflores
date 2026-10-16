"""The independent checks must find the packet's planted errors from the data alone."""
from app.checks import run_checks
from app.packet import get_packet

P = get_packet()
F = {f["id"]: f for f in run_checks(P)}


def test_packet_loaded_as_delivered():
    assert len(P.data["documents"]) == 74
    assert len(P.data["extracted_values"]) == 3012
    assert P.current_version == "v3"


def test_engine_arithmetic_foots():
    assert F["ENGINE_ARITHMETIC"]["severity"] == "info"  # all summed lines foot: errors are in inputs and rules


def test_rsu_basis_blank_read_as_zero():
    f = F["RSU_BASIS_ZERO"]
    assert sum(-x["delta"] for x in f["proposed"]) == 47620
    assert "EXTRACT_BLANK_AS_ZERO" in F


def test_1099k_double_count():
    assert F["SCHC_1099K_DOUBLE"]["expected_value"] == 151300


def test_mileage_duplicate_page():
    assert F["MILEAGE_DUP_PAGE"]["expected_value"] == 8100
    assert "DUP_PAGE_D23_3" in F


def test_sehi_disallowed():
    assert F["SEHI_NOT_ALLOWED"]["proposed"][0]["delta"] == -14400


def test_payments_agree_to_agency_records():
    assert F["FED_ESTIMATES_VS_IRS"]["expected_value"] == 12000
    assert F["CA_ESTIMATES_VS_FTB"]["expected_value"] == 10500


def test_california_wage_sourcing():
    assert F["CA_WAGES_SOURCE"]["expected_value"] == 129569


def test_itemized_errors():
    assert F["MORTGAGE_PAYOFF_DOUBLE"]["proposed"][0]["delta"] == -2150
    assert F["VEHICLE_DONATION_VALUE"]["expected_value"] == 2900
    assert F["HOME_TAX_PRORATION"]["expected_value"] == 6508


def test_identity_and_extraction():
    assert F["DEPENDENT_SSN"]["expected_value"] == "666-74-3390"
    assert any(k.startswith("EXTRACT_NOT_PRINTED_ev-1045") for k in F)  # transposed provider EIN


def test_review_corrections_built_in():
    assert F["SEP_EXCESS"]["expected_value"] == 13674
    assert F["CA_OSTC_OREGON"]["proposed"][0]["delta"] == -844
    assert "DAF_ACK" in F


def test_every_finding_cites_evidence():
    for f in F.values():
        assert f["refs"], f["id"]
