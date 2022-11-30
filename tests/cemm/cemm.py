from dataclasses import dataclass

# noinspection PyPep8Naming
from tests.support.quantized_decimal import QuantizedDecimal as D
from functools import cached_property
from math import cos, sin, pi

# import dfuzzy
# from dfuzzy import isle, isge
from typing import Optional

from tests.support.dfuzzy import (
    isclose,
    prec_sanity_check,
    soft_clamp,
    sqrt,
    prec_input,
)

##################################################################################################################
### Note this is an old implementation with low precision, see cemm_prec_implementation for new implementation ###
##################################################################################################################


Vector = tuple[
    D, D
]  # Purely a shorthand. We don't use any vector math libraries in this code!

pi_d = D(pi)


def angle2rotationpoint(phi: D):
    # You can use this for rx and ry in Params.
    return D(cos(phi)), D(sin(phi))


def eta(pxc: D) -> Vector:
    """Calculates from a price _pxc wrt. the untransformed circle a point t'' wrt. the untransformed circle,
    up to a factor r. We have price _pxc on the untransformed circle at point -r * eta(_pxc).

    _pxc unconstrained in (-∞, ∞), since we're on the untransformed circle.

    This is somewhat expensive to compute b/c it uses a square root.

    Lemma 4."""
    # TODO rename to make clearer
    z = sqrt(D(1) + pxc**2)
    return pxc / z, D(1) / z


@dataclass
class Params:
    # Price bounds. alpha and beta in the writeup.
    # Require alpha < 1 < beta.
    alpha: D
    beta: D

    # x and y coordinates of the rotation point. Rotation of the ellipse is s.t. (0, 1) maps to (rx, ry).
    # Require rx**2 + ry**2 == 1.
    # In sane cases, we have ry < 0 < rx.
    # In the writeup, rx = cos(φ) and ry = sin(φ) so that c = rx and s = -ry.
    rx: D
    ry: D

    # Stretching factor. 1 is a circle, ∞ would be a line (degenerate ellipse)
    # Require l >= 1.
    # λ in the writeup.
    l: D

    # The matrices A and A^{-1} are kept implicitly. See the writeup, section 2.2, for what they are.

    @staticmethod
    def from_angle_degrees(alpha: D, beta: D, phi: D, l: D):
        assert phi <= 0  # Not strictly required but catches a common mistake.
        return Params(alpha, beta, *angle2rotationpoint(phi * 2 * pi_d / 360), l)

    # Shorthands:

    @cached_property
    def c(self):
        return self.rx

    @cached_property
    def s(self):
        return -self.ry

    def zeta(self, px: D):
        """Transform a price px of the transformed circle (i.e., the ellipse) into a price _pxc of the untransformed
        circle s.t. we have price px at a point of the transformed circle iff we have price _pxc at the corresponding
        (via the transformation) point of the untransformed circle.

        This ignores translation offsets (in both cases).

        Proposition 5 instantiated to what A is for us."""
        # todo maybe refactor:
        d, n = self.A_times(D(-1), px)
        return -n / d
        # n = -self.s + px * self.c
        # d = -self.c / self.l - px * self.s / self.l
        # return -n / d

    def tau(self, px: D) -> Vector:
        """-r * tau(px) is the point on the untransformed circle corresponding to price px on the transformed circle."""
        return eta(self.zeta(px))

    # The following two are somewhat expensive to compute and we may therefore want to cache them in the solidity
    # implementation, too. A comparison should be done though.

    @cached_property
    def tau_alpha(self) -> Vector:
        return self.tau(self.alpha)

    @cached_property
    def tau_beta(self) -> Vector:
        return self.tau(self.beta)

    # Aliases to make this duck-compatible with 'DerivedParams' from cemm_prec_implementation.py as long as only the
    # tau values are accessed.
    @property
    def tauAlpha(self) -> Vector:
        return self.tau_alpha

    @property
    def tauBeta(self) -> Vector:
        return self.tau_beta

    def Ainv_times(self, x: D, y: D) -> Vector:
        """A^{-1} . (x, y), where '.' is matrix-vector multiplication and A is the transformation matrix."""
        retx = x * self.l * self.c + self.s * y
        rety = -x * self.l * self.s + self.c * y
        return retx, rety

    # x and y coordinates of the above. These could be inlined in the final implementation.
    def Ainv_times_x(self, x: D, y: D) -> D:
        return x * self.l * self.c + self.s * y

    def Ainv_times_y(self, x: D, y: D) -> D:
        return -x * self.l * self.s + self.c * y

    def A_times(self, x: D, y: D) -> Vector:
        """A . (x, y)."""
        retx = self.c * x / self.l - self.s * y / self.l
        rety = self.s * x + self.c * y
        return retx, rety

    # x and y coordinates
    def A_times_x(self, x: D, y: D) -> D:
        return self.c * x / self.l - self.s * y / self.l

    def A_times_y(self, x: D, y: D) -> D:
        return self.s * x + self.c * y


# For testing
myparams1 = Params.from_angle_degrees(D("0.8"), D(1) / D("0.8"), D("-45"), D("2"))
myparams2_circle = Params.from_angle_degrees(D("0.8"), D(1) / D("0.8"), D(0), D(1))


def scalarprod(x1: D, y1: D, x2: D, y2: D) -> D:
    return x1 * x2 + y1 * y2


@dataclass  # Mainly to get automatic repr()
class CEMM:
    params: Params
    x: D
    y: D
    r: D

    def __init__(self, params: Params):
        self.params = params
        self.x = D(0)
        self.y = D(0)
        # self.a = D(0)
        # self.b = D(0)
        self.r = D(0)

    @staticmethod
    def from_x_y(x: D, y: D, params: Params):
        """Initialize from real reserves x, y.

        Proposition 12."""
        ret = CEMM(params)
        ret.x = x
        ret.y = y
        at: Vector = params.A_times(x, y)
        # NOTE: What are currently arguments to A_times() will probably be completely cached in the future.
        achi: Vector = params.A_times(
            params.Ainv_times_x(*params.tau_beta),
            params.Ainv_times_y(*params.tau_alpha),
        )
        a = scalarprod(*achi, *achi) - D(1)
        b = scalarprod(*at, *achi)
        c = scalarprod(*at, *at)
        d = b**2 - a * c
        dr = sqrt(d)
        ret.r = (b + dr) / a
        return ret

    @staticmethod
    def from_px_r(px: D, r: D, params: Params):
        """Proposition 8"""
        # Sanity check. If this is not the case, the following yields a negative reserve point. - Which is ok
        # mathematically, but almost never what we mean.
        # This check fails sometimes due to numerical errors:
        # assert params.alpha <= px <= params.beta
        px = soft_clamp(px, params.alpha, params.beta, prec_input)

        ret = CEMM(params)
        ret.r = r
        taupx: Vector = params.tau(
            px
        )  # Compute these in one step b/c then we only need one square root.
        ret.x = r * (
            params.Ainv_times_x(*params.tau_beta) - params.Ainv_times_x(*taupx)
        )
        ret.y = r * (
            params.Ainv_times_y(*params.tau_alpha) - params.Ainv_times_y(*taupx)
        )
        return ret

    @staticmethod
    def from_px_v(px: D, v: D, params: Params):
        """
        Initialize from price and portfolio value. This is nice b/c portfolio value is comparable across parameter
        choices and also with other AMMs. (which r need not be)

        Proposition 9, applied in reverse, paired with `from_px_r()`."""
        px = soft_clamp(px, params.alpha, params.beta, prec_input)

        taupx = params.tau(px)  # Somewhat expensive
        xn = params.Ainv_times_x(*params.tau_beta) - params.Ainv_times_x(*taupx)
        yn = params.Ainv_times_y(*params.tau_alpha) - params.Ainv_times_y(*taupx)
        r = v / (px * xn + yn)
        return CEMM.from_px_r(px, r, params)

    # Offsets. Note that, in contrast to (say) virtual reserve offsets, these are *subtracted* from the real reserve.
    # Equivalently, we shift the curve up-right rather than down-left.
    # For the formulas see Proposition 7.
    # For implementation: These are fast to compute. Caching them is probably not worth it, though this should be
    # reviewed.
    @property
    def a(self):
        return self.r * self.params.Ainv_times_x(*self.params.tau_beta)

    @property
    def b(self):
        return self.r * self.params.Ainv_times_y(*self.params.tau_alpha)

    # Exhaustion points x^+, y^+. See Prop 7.
    @property
    def xmax(self):
        return self.a - self.r * self.params.Ainv_times_x(*self.params.tau_alpha)

    @property
    def ymax(self):
        return self.b - self.r * self.params.Ainv_times_y(*self.params.tau_beta)

    @property
    def _pxc(self):
        """Price in the untransformed circle for the point corresponding to the current reserve state."""
        xp, yp = self.x - self.a, self.y - self.b
        xpp, ypp = self.params.A_times(xp, yp)
        return xpp / ypp  # Price formula for the circle

    @property
    def _sqrtOnePlusZetaSquared(self):
        """Uses 2.1.7 equation 7 to calculate sqrt(1+zeta(px)^2) without having to calculate this formula explicitly."""
        xp, yp = self.x - self.a, self.y - self.b
        xpp, ypp = self.params.A_times(xp, yp)
        return -self.r / ypp

    @property
    def px(self):
        """Current instantaneous price. See general theory at the beginning of section 2."""
        pxc = self._pxc
        axx, ayx = self.params.A_times(D(1), D(0))
        axy, ayy = self.params.A_times(D(0), D(1))
        return (pxc * axx + ayx) / (pxc * axy + ayy)

    @property
    def _tau_px(self):
        """tau(px) where px is the price offered by the AMM at the current state.

        Definition of tau and eta together with the comment on computing sqrt(1 + _pxc^2) in section 2.1.5."""
        pxcz = -self.r / self.params.A_times_y(self.x - self.a, self.y - self.b)
        return self._pxc / pxcz, 1 / pxcz

    @property
    def pf_value(self):
        """Portfolio value. Proposition 10."""
        taupx = self._tau_px
        nx = self.params.Ainv_times_x(*self.params.tau_beta) - self.params.Ainv_times_x(
            *taupx
        )
        ny = self.params.Ainv_times_y(
            *self.params.tau_alpha
        ) - self.params.Ainv_times_y(*taupx)
        return self.r * (self.px * nx + ny)

    def show_invariant_r(self):
        """For testing. Calculate the LHS, RHS of the invariant based on r. These should be equal."""
        xpp, ypp = self.params.A_times(self.x - self.a, self.y - self.b)
        return xpp**2 + ypp**2, self.r**2

    def trade_x(self, dx: D, mock: bool = False) -> Optional[D]:
        """Proposition 11. Trade a given amount of x for y.

        Returns: amount dy redeemed / to be paid. Without fees.

        Returns None and changes nothing if the trade is not possible given the current reserve.

        Signs for dx and the return value refer to how the *reserve* changes. So paying to the reserve = positive; receiving from the reserve = negative."""
        xnew = self.x + dx
        ynew = self._compute_y_for_x(xnew)
        if ynew is None:
            return None
        if not mock:
            self.x = xnew
            yold = self.y
            self.y = ynew
        else:
            yold = self.y
        return ynew - yold

    def trade_y(self, dy: D, mock: bool = False) -> Optional[D]:
        """Proposition 11. Trade a given amount of y for x. Analogous to `trade_y()`."""
        ynew = self.y + dy
        xnew = self._compute_x_for_y(ynew)
        if xnew is None:
            return None
        if not mock:
            self.y = ynew
            xold = self.x
            self.x = xnew
        else:
            xold = self.x
        return xnew - xold

    def _compute_y_for_x(self, x: D, nomaxvals: bool = False) -> Optional[D]:
        """Depends on the current invariant r. Return None iff this x value is impossible given the current
        invariant.

        nomaxvals: For TESTING only. Don't use xmax and ymax to determine legitimacy, but instead check if the result of the trade would not be allowed."""
        if x < 0:
            return None

        if not nomaxvals and x > self.xmax:
            return None

        xp = x - self.a

        ls = 1 - 1 / self.params.l**2  # λ underlined in the prop.
        s = self.params.s
        c = self.params.c

        d = s**2 * c**2 * ls**2 * xp**2 - (1 - ls * s**2) * (
            (1 - ls * c**2) * xp**2 - self.r**2
        )
        dr = sqrt(d)
        yp = (-s * c * ls * xp - dr) / (1 - ls * s**2)

        y = yp + self.b

        # Sanity check
        if y < 0:
            assert nomaxvals  # Sanity check: We should only be able to reach this point if we didn't check for xmax above.
            return None

        return y

    def _compute_x_for_y(self, y: D, nomaxvals: bool = False) -> Optional[D]:
        if y < 0:
            return None

        if not nomaxvals and y > self.ymax:
            return None

        ls = 1 - 1 / self.params.l**2  # λ underlined in the prop.
        s = self.params.s
        c = self.params.c

        yp = y - self.b

        d = s**2 * c**2 * ls**2 * yp**2 - (1 - ls * c**2) * (
            (1 - ls * s**2) * yp**2 - self.r**2
        )
        dr = sqrt(d)
        xp = (-s * c * ls * yp - dr) / (1 - ls * c**2)

        x = xp + self.a

        # Sanity check
        if x < 0:
            assert nomaxvals
            return None

        return x

    def update_liquidity(self, dr, mock: bool = False):
        """Change the invariant by dr by adding or removing liquidity.

        Returns: (x, y) reserves to be paid/received. Sign is from the perpective of the mechanism, so that x > 0
        means the LPer needs to pay.

        mock: Don't actually change any state vars."""
        assert dr >= -self.r

        # TODO this code is duplicated a few times. May make sense to give it a name.
        taupx = self._tau_px
        taupx1 = self.params.tau(self.px)  # DEBUG
        params = self.params
        xn = params.Ainv_times_x(*params.tau_beta) - params.Ainv_times_x(*taupx)
        yn = params.Ainv_times_y(*params.tau_alpha) - params.Ainv_times_y(*taupx)

        dx, dy = dr * xn, dr * yn
        if not mock:
            self.r += dr
            self.x += dx
            self.y += dy
        return dx, dy

    def assert_isclose_to(self, mm, prec: D):  # mm: CEMM
        assert (
            isclose(self.x, mm.x, prec)
            and isclose(self.y, mm.y, prec)
            and isclose(self.r, mm.r, prec)
        )


def mtest_rebuild_r(mm: CEMM):
    mm1 = CEMM.from_x_y(mm.x, mm.y, mm.params)
    print(mm.r, mm1.r)
    assert isclose(mm.r, mm1.r, prec_sanity_check)
