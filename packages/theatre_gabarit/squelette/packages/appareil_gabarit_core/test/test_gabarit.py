from conftest import PKG
from theatre_gabarit.essais import verifier_appareil


def test_gabarit():
    gestes = verifier_appareil(PKG)
    assert not gestes, "gestes restants (README du gabarit) :\n" + "\n".join(gestes)
