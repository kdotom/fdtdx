from typing import Literal

import pytreeclass as tc
import jax
import jax.numpy as jnp

from fdtdx.core.plotting.colors import DARK_GREY
from fdtdx.objects.boundaries.boundary_utils import (
    kappa_from_direction_axis, 
    standard_sigma_from_direction_axis,
)
from fdtdx.core.jax.typing import (
    Slice3D,
    SliceTuple3D,
    GridShape3D
)
from fdtdx.objects.material import NoMaterial


@tc.autoinit
class BoundaryState(tc.TreeClass):
    psi_Ex: jax.Array
    psi_Ey: jax.Array
    psi_Ez: jax.Array
    psi_Hx: jax.Array
    psi_Hy: jax.Array
    psi_Hz: jax.Array
    # phi_E: jax.Array
    # phi_H: jax.Array
    bE: jax.Array
    bH: jax.Array
    cE: jax.Array
    cH: jax.Array
    kappa: jax.Array

@tc.autoinit
class PerfectlyMatchedLayer(NoMaterial):
    axis: int = tc.field(init=True, kind="KW_ONLY")  # type: ignore
    direction: Literal["+", "-"] = tc.field( # type: ignore
        init=True, 
        kind="KW_ONLY",
        on_getattr=[tc.unfreeze],
        on_setattr=[tc.freeze],
    )
    alpha: float = 1.0e-8
    kappa_start: float = 1.0
    kappa_end: float = 1.5
    color: tuple[float, float, float] = DARK_GREY
    
    @property
    def descriptive_name(self) -> str:
        axis_str = (
            "x" if self.axis == 0 
            else "y" if self.axis == 1 
            else "z"
        )
        direction_str = "min" if self.direction == "-" else "max"
        return f"{direction_str}_{axis_str}"
    
    @property
    def thickness(self) -> int:
        return self.grid_shape[self.axis]

    def init_state(
        self,
    ) -> BoundaryState:

        dtype = self._config.dtype
        sigma_E, sigma_H = standard_sigma_from_direction_axis(
            thickness=self.thickness,
            direction=self.direction,
            axis=self.axis,
            dtype=dtype,
        )
        
        kappa = kappa_from_direction_axis(
            kappa_start=self.kappa_start,
            kappa_end=self.kappa_end,
            thickness=self.thickness,
            direction=self.direction,
            axis=self.axis,
            dtype=dtype,
        )
        
        bE = jnp.exp(-self._config.courant_number * (sigma_E / kappa + self.alpha))
        bH = jnp.exp(-self._config.courant_number * (sigma_H / kappa + self.alpha))

        cE = (bE - 1) * sigma_E / (sigma_E * kappa + kappa**2 * self.alpha)
        cH = (bH - 1) * sigma_H / (sigma_H * kappa + kappa**2 * self.alpha)
        
        ext_shape = (3,) + self.grid_shape

        boundary_state = BoundaryState(
            psi_Ex=jnp.zeros(shape=ext_shape, dtype=dtype),
            psi_Ey=jnp.zeros(shape=ext_shape, dtype=dtype),
            psi_Ez=jnp.zeros(shape=ext_shape, dtype=dtype),
            psi_Hx=jnp.zeros(shape=ext_shape, dtype=dtype),
            psi_Hy=jnp.zeros(shape=ext_shape, dtype=dtype),
            psi_Hz=jnp.zeros(shape=ext_shape, dtype=dtype),
            bE=bE.astype(dtype),
            bH=bH.astype(dtype),
            cE=cE.astype(dtype),
            cH=cH.astype(dtype),
            kappa=kappa.astype(dtype),
        )
        return boundary_state
    
    
    def reset_state(self, state: BoundaryState) -> BoundaryState:
        dtype = self._config.dtype
        sigma_E, sigma_H = standard_sigma_from_direction_axis(
            thickness=self.thickness,
            direction=self.direction,
            axis=self.axis,
            dtype=dtype,
        )
        
        kappa = kappa_from_direction_axis(
            kappa_start=self.kappa_start,
            kappa_end=self.kappa_end,
            thickness=self.thickness,
            direction=self.direction,
            axis=self.axis,
            dtype=dtype,
        )
        
        bE = jnp.exp(-self._config.courant_number * (sigma_E / kappa + self.alpha))
        bH = jnp.exp(-self._config.courant_number * (sigma_H / kappa + self.alpha))

        cE = (bE - 1) * sigma_E / (sigma_E * kappa + kappa**2 * self.alpha)
        cH = (bH - 1) * sigma_H / (sigma_H * kappa + kappa**2 * self.alpha)
        
        new_state = BoundaryState(
            psi_Ex=state.psi_Ex * 0,
            psi_Ey=state.psi_Ey * 0,
            psi_Ez=state.psi_Ez * 0,
            psi_Hx=state.psi_Hx * 0,
            psi_Hy=state.psi_Hy * 0,
            psi_Hz=state.psi_Hz * 0,
            bE=bE.astype(dtype),
            bH=bH.astype(dtype),
            cE=cE.astype(dtype),
            cH=cH.astype(dtype),
            kappa=kappa.astype(dtype),
        )
        return new_state
    

    def boundary_interface_grid_shape(self) -> GridShape3D:
        if self.axis == 0:
            return 1, self.grid_shape[1], self.grid_shape[2]
        elif self.axis == 1:
            return self.grid_shape[0], 1, self.grid_shape[2]
        elif self.axis == 2:
            return self.grid_shape[0], self.grid_shape[1], 1
        raise Exception(f"Invalid axis: {self.axis=}")
    
    def boundary_interface_slice_tuple(self) -> SliceTuple3D:
        slice_list = [*self._grid_slice_tuple]
        if self.direction == "+":
            slice_list[self.axis] = (
                self._grid_slice_tuple[self.axis][0],
                self._grid_slice_tuple[self.axis][0] + 1
            )
        elif self.direction == "-":
            slice_list[self.axis] = (
                self._grid_slice_tuple[self.axis][1] - 1,
                self._grid_slice_tuple[self.axis][1]
            )
        return slice_list[0], slice_list[1], slice_list[2]
    
    def boundary_interface_slice(self) -> Slice3D:
        slice_list = [*self.grid_slice]
        if self.direction == "+":
            slice_list[self.axis] = slice(
                self._grid_slice_tuple[self.axis][0],
                self._grid_slice_tuple[self.axis][0] + 1
            )
        elif self.direction == "-":
            slice_list[self.axis] = slice(
                self._grid_slice_tuple[self.axis][1] - 1,
                self._grid_slice_tuple[self.axis][1]
            )
        return slice_list[0], slice_list[1], slice_list[2]
        

    def update_E_boundary_state(
        self,
        boundary_state: BoundaryState,
        H: jax.Array,
    ) -> BoundaryState:
        
        Hx = H[0, *self.grid_slice]
        Hy = H[1, *self.grid_slice]
        Hz = H[2, *self.grid_slice]

        psi_Ex = boundary_state.psi_Ex * boundary_state.bE
        psi_Ey = boundary_state.psi_Ey * boundary_state.bE
        psi_Ez = boundary_state.psi_Ez * boundary_state.bE

        psi_Ex = psi_Ex.at[1, :, 1:, :].add(
            (Hz[:, 1:, :] - Hz[:, :-1, :]) * 
            (boundary_state.cE[1, :, 1:, :] if self.axis == 1 else boundary_state.cE[1])
        )
        psi_Ex = psi_Ex.at[2, :, :, 1:].add(
            (Hy[:, :, 1:] - Hy[:, :, :-1]) * 
            (boundary_state.cE[2, :, :, 1:] if self.axis == 2 else boundary_state.cE[2])
        )

        psi_Ey = psi_Ey.at[2, :, :, 1:].add(
            (Hx[:, :, 1:] - Hx[:, :, :-1]) * 
            (boundary_state.cE[2, :, :, 1:] if self.axis == 2 else boundary_state.cE[2])
        )
        psi_Ey = psi_Ey.at[0, 1:, :, :].add(
            (Hz[1:, :, :] - Hz[:-1, :, :]) * 
            (boundary_state.cE[0, 1:, :, :] if self.axis == 0 else boundary_state.cE[0])
        )

        psi_Ez = psi_Ez.at[0, 1:, :, :].add(
            (Hy[1:, :, :] - Hy[:-1, :, :]) *
            (boundary_state.cE[0, 1:, :, :] if self.axis == 0 else boundary_state.cE[0])
        )
        psi_Ez = psi_Ez.at[1, :, 1:, :].add(
            (Hx[:, 1:, :] - Hx[:, :-1, :]) * 
            (boundary_state.cE[1, :, 1:, :] if self.axis == 1 else boundary_state.cE[1])
        )

        boundary_state = boundary_state.at['psi_Ex'].set(psi_Ex)
        boundary_state = boundary_state.at['psi_Ey'].set(psi_Ey)
        boundary_state = boundary_state.at['psi_Ez'].set(psi_Ez)
        
        return boundary_state


    def update_H_boundary_state(
        self,
        boundary_state: BoundaryState,
        E: jax.Array,
    ) -> BoundaryState:

        Ex = E[0, *self.grid_slice]
        Ey = E[1, *self.grid_slice]
        Ez = E[2, *self.grid_slice]

        psi_Hx = boundary_state.psi_Hx * boundary_state.bH
        psi_Hy = boundary_state.psi_Hy * boundary_state.bH
        psi_Hz = boundary_state.psi_Hz * boundary_state.bH

        psi_Hx = psi_Hx.at[1, :, :-1, :].add(
            (Ez[:, 1:, :] - Ez[:, :-1, :]) * 
            (boundary_state.cH[1, :, :-1, :] if self.axis == 1 else boundary_state.cH[1])
        )
        psi_Hx = psi_Hx.at[2, :, :, :-1].add(
            (Ey[:, :, 1:] - Ey[:, :, :-1]) *
            (boundary_state.cH[2, :, :, :-1] if self.axis == 2 else boundary_state.cH[2])
        )

        psi_Hy = psi_Hy.at[2, :, :, :-1].add(
            (Ex[:, :, 1:] - Ex[:, :, :-1]) *
            (boundary_state.cH[2, :, :, :-1] if self.axis == 2 else boundary_state.cH[2])
        )
        psi_Hy = psi_Hy.at[0, :-1, :, :].add(
            (Ez[1:, :, :] - Ez[:-1, :, :]) *
            (boundary_state.cH[0, :-1, :, :] if self.axis == 0 else boundary_state.cH[0])
        )

        psi_Hz = psi_Hz.at[0, :-1, :, :].add(
            (Ey[1:, :, :] - Ey[:-1, :, :]) *
            (boundary_state.cH[0, :-1, :, :] if self.axis == 0 else boundary_state.cH[0])
        )
        psi_Hz = psi_Hz.at[1, :, :-1, :].add(
            (Ex[:, 1:, :] - Ex[:, :-1, :]) *
            (boundary_state.cH[1, :, :-1, :] if self.axis == 1 else boundary_state.cH[1])
        )

        boundary_state = boundary_state.at['psi_Hx'].set(psi_Hx)
        boundary_state = boundary_state.at['psi_Hy'].set(psi_Hy)
        boundary_state = boundary_state.at['psi_Hz'].set(psi_Hz)
        
        return boundary_state


    def update_E(
        self,
        E: jax.Array,
        boundary_state: BoundaryState,
        inverse_permittivity: jax.Array,
    ):
        phi_Ex = boundary_state.psi_Ex[1] - boundary_state.psi_Ex[2]
        phi_Ey = boundary_state.psi_Ey[2] - boundary_state.psi_Ey[0]
        phi_Ez = boundary_state.psi_Ez[0] - boundary_state.psi_Ez[1]
        phi_E = jnp.stack((phi_Ex, phi_Ey, phi_Ez), axis=0)

        E = E.at[:, *self.grid_slice].divide(boundary_state.kappa)
        inv_perm_slice = inverse_permittivity[self.grid_slice]
        update = self._config.courant_number * inv_perm_slice * phi_E
        E = E.at[:, *self.grid_slice].add(update)
        return E

    def update_H(
        self,
        H: jax.Array,
        boundary_state: BoundaryState,
        inverse_permeability: jax.Array,
    ):
        phi_Hx = boundary_state.psi_Hx[1] - boundary_state.psi_Hx[2]
        phi_Hy = boundary_state.psi_Hy[2] - boundary_state.psi_Hy[0]
        phi_Hz = boundary_state.psi_Hz[0] - boundary_state.psi_Hz[1]
        phi_H = jnp.stack((phi_Hx, phi_Hy, phi_Hz), axis=0)
        
        H = H.at[:, *self.grid_slice].divide(boundary_state.kappa)
        inv_perm_slice = inverse_permeability[self.grid_slice]
        update = -self._config.courant_number * inv_perm_slice * phi_H
        H = H.at[:, *self.grid_slice].add(update)
        return H
    
    



