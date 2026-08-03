from commercial_kernel import CommercialKernel, UsageEvent


def test_catalogue_and_quote():
    kernel = CommercialKernel()
    catalogue = kernel.catalogue()
    assert len(catalogue) == 3
    quote = kernel.quote("AO-PILOT", 12)
    assert quote["contract_value_zar"] == 560_000


def test_metering_and_margin():
    kernel = CommercialKernel()
    usage = kernel.meter([
        UsageEvent("TENANT-1", "build", 2, 2500),
        UsageEvent("TENANT-1", "support_hour", 5, 900),
    ])
    assert usage["cost_zar"] == 9500
    economics = kernel.unit_economics("AO-PILOT", 12_000)
    assert economics["commercially_healthy"] is True
    assert economics["gross_margin"] == 0.6


def test_invalid_term():
    kernel = CommercialKernel()
    try:
        kernel.quote("AO-PILOT", 0)
    except ValueError:
        return
    raise AssertionError("expected ValueError")
