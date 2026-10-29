from seed_intel.content.compliance_checker import check_compliance


def test_compliance_checker():
    assert check_compliance("参加就能保录取")["risk_level"] == "high"
    assert check_compliance("适合申请方向明确的学生")["risk_level"] == "low"
