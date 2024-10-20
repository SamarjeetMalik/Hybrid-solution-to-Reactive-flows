from phi.flow import *
from phi import math, struct
import tensorflow as tf

@struct.definition()
class SpFluid(DomainState):
    """
    A Fluid state consists of a density field (centered grid) and a velocity field (staggered grid).
    """

    def __init__(self, domain, velocity=0.0, temperature=0.0, density=0.0, pressure=101325, rd=0.0, Yf=0.0, Yo=0.0, Wt=0.0, Wkf=0.0, Wko=0.0, buoyancy_factor=0.0, amp=1.0, eq=1.0, tags=('fluid', 'velocityfield'), name='fluid', **kwargs):
        DomainState.__init__(self, **struct.kwargs(locals()))
        self.solve_info = {}

    def default_physics(self): return SpeciesEnergy

    @struct.variable(default=0, dependencies=DomainState.domain)
    def temperature(self, temperature):
        """
The marker temperature is stored in a CenteredGrid with dimensions matching the domain.
        """
        return self.centered_grid('temperature', temperature)

    @struct.variable(default=0, dependencies=DomainState.domain)
    def density(self, density):
        return self.centered_grid('density', density)

    @struct.variable(default=101325, dependencies=DomainState.domain)
    def pressure(self, pressure):
        """
The marker pressure is stored in a CenteredGrid with dimensions matching the domain.
        """
        return self.centered_grid('pressure', pressure)

    @struct.variable(default=0, dependencies=DomainState.domain)
    def rd(self, rd):
        return self.centered_grid('rd', rd)

    @struct.variable(default=0, dependencies=DomainState.domain)
    def Yf(self, Yf):
        """
The marker pressure is stored in a CenteredGrid with dimensions matching the domain.
        """
        return self.centered_grid('Yf', Yf)

    @struct.variable(default=0, dependencies=DomainState.domain)
    def Yo(self, Yo):
        """
The marker pressure is stored in a CenteredGrid with dimensions matching the domain.
        """
        return self.centered_grid('Yo', Yo)

    @struct.variable(default=0, dependencies=DomainState.domain)
    def Wt(self, Wt):
        """
The marker pressure is stored in a CenteredGrid with dimensions matching the domain.
        """
        return self.centered_grid('Wt', Wt)

    @struct.variable(default=0, dependencies=DomainState.domain)
    def Wkf(self, Wkf):
        """
The marker pressure is stored in a CenteredGrid with dimensions matching the domain.
        """
        return self.centered_grid('Wkf', Wkf)

    @struct.variable(default=0, dependencies=DomainState.domain)
    def Wko(self, Wko):
        """
The marker pressure is stored in a CenteredGrid with dimensions matching the domain.
        """
        return self.centered_grid('Wko', Wko)

    @struct.constant(default=1.0)
    def amp(self, amp):
        return amp

    @struct.constant(default=1.0)
    def eq(self, eq):
        return eq

    @struct.variable(default=0, dependencies=DomainState.domain)
    def velocity(self, velocity):
        """
The velocity is stored in a StaggeredGrid with dimensions matching the domain.
        """
        return self.staggered_grid('velocity', velocity)

    @struct.constant(default=0.0)
    def buoyancy_factor(self, fac):
        """
The default fluid physics can apply Boussinesq buoyancy as an upward force, proportional to the density.
This force is scaled with the buoyancy_factor (float).
        """
        return fac

    def __repr__(self):
        return "Fluid[velocity: %s, temperature: %s, density: %s, pressure: %s, rd: %s, Yf: %s, Yo: %s, Wt: %s, Wkf: %s, Wko: %s]" % (self.velocity, self.temperature, self.density, self.pressure, self.rd, self.Yf, self.Yo, self.Wt, self.Wkf, self.Wko)

def divergence_free(velocity, density, domain=None, obstacles=(), pressure_solver=None, return_info=False):
    """
Projects the given velocity field by solving for and subtracting the pressure.
    :param return_info: if True, returns a dict holding information about the solve as a second object
    :param velocity: StaggeredGrid
    :param domain: Domain matching the velocity field, used for boundary conditions
    :param obstacles: list of Obstacles
    :param pressure_solver: PressureSolver. Uses default solver if none provided.
    :return: divergence-free velocity as StaggeredGrid
    """
    assert isinstance(velocity, StaggeredGrid)
    # --- Set up FluidDomain ---
    if domain is None:
        domain = Domain(velocity.resolution, OPEN)
    obstacle_mask = union_mask([obstacle.geometry for obstacle in obstacles])
    if obstacle_mask is not None:
        obstacle_grid = obstacle_mask.at(velocity.center_points).copied_with(extrapolation='constant')
        active_mask = 1 - obstacle_grid
    else:
        active_mask = math.ones(domain.centered_shape(name='active', extrapolation='constant'))
    accessible_mask = active_mask.copied_with(extrapolation=Material.accessible_extrapolation_mode(domain.boundaries))
    fluiddomain = FluidDomain(domain, active=active_mask, accessible=accessible_mask)
    # --- Boundary Conditions, Pressure Solve ---
    rho_u = velocity * density.at(velocity)
    divergence_field = rho_u.divergence(physical_units=False)
    #divergence_field = velocity.divergence(physical_units=False)
    pressure_c, iterations = solve_pressure(divergence_field, fluiddomain, pressure_solver=pressure_solver)
    pressure_c *= velocity.dx[0]
    gradp = StaggeredGrid.gradient(pressure_c)
    velocity -= fluiddomain.with_hard_boundary_conditions(gradp / density.at(velocity))
    #velocity -= fluiddomain.with_hard_boundary_conditions(gradp)
    #print('velocity 2', np.mean(velocity._data[0]._data))
    return velocity if not return_info else (velocity, {'pressure_c': pressure_c, 'iterations': iterations, 'divergence': divergence_field})


fuel_type = 'methane'
if fuel_type == 'methane':
    A_m, n_m, E_m = 5.1E4, 0, 93600
    hk, cp = 5.01E7, 1450
    Wf, Wo, Wp = 0.016, 0.032, 0.062
    Vf, Vo = -1, -2
elif fuel_type == 'propane':
    A_m, n_m, E_m = 2.75e8, 0, 130317
    hk, cp = 4.66E7, 1300
    Wf, Wo, Wp = 0.044, 0.032, 0.062
    Vf, Vo = -1, -5

def get_min_max_zf_zo(eq):
    eq_min = 0.8
    eq_max = 1.0
    Zf_min, Zf_max = 1/(1 + (4*4.29/eq_min)),  1/(1 + (4*4.29/eq_max))
    Zo_min, Zo_max = (1-Zf_max), (1-Zf_min)
    return Zf_min, Zf_max, Zo_min, Zo_max

def get_zf_bc_vector(rd_yk, equi_ratio):
    Zf_min, Zf_max, Zo_min, Zo_max = get_min_max_zf_zo(equi_ratio)
    zf_bc = (rd_yk)*(Zf_max - Zf_min) + Zf_min  # Zf_max
    return zf_bc

def VelocityBoundary_y(field, rd_array, res, rd_yk, equi_ratio):
    vn = np.zeros(field.data[0].data.shape)  # NOTE: st.velocity.data[1] is considered as the velocity field in x axis!

    vn[0, 0:1, 0:res, 0] = np.absolute(rd_array[0:1, 0:res, 0]) * 4 + 6
    vn[0, 0:1, res:(res + 1), 0] = np.absolute(rd_array[0:1, -1, 0]) * 4 + 6

    velBCy = vn
    vm = np.ones(field.data[0].data.shape)  # NOTE: st.velocity.data[1] is considered as the velocity field in x axis!
    vm[:, 0:1, :, 0] = 0  # bottom uy
    vm[:, int(res / 4):, 0:1, 0] = 0.0  # upper left wall
    vm[:, int(res / 4):, (res - 1):, 0] = 0.0  # upper right wall
    velBCyMask = vm
    return velBCy, velBCyMask

def VelocityBoundary_x(field):
    vn = np.ones(field.data[1].data.shape)  # NOTE: st.velocity.data[1] is considered as the velocity field in x axis!
    vn[:, 0:1, :, 0] = 0.0 # bottom ux
    velBCx = vn
    velBCxMask = np.copy(vn)
    return velBCx, velBCxMask


class SpEnergy(Physics):
    """
Physics modelling the incompressible Navier-Stokes equations.
Supports buoyancy proportional to the marker density.
Supports obstacles, density effects, velocity effects, global gravity.
    """

    def __init__(self, pressure_solver=None):
        Physics.__init__(self, [StateDependency('obstacles', 'obstacle'),
                                StateDependency('gravity', 'gravity', single_state=True),
                                StateDependency('density_effects', 'density_effect', blocking=True),
                                StateDependency('velocity_effects', 'velocity_effect', blocking=True)])
        self.pressure_solver = pressure_solver

    def step(self, fluid, rd_array, res, dt=1.0, obstacles=(), gravity=Gravity(), density_effects=(), velocity_effects=()):
        # pylint: disable-msg = arguments-differ
        diffusion_substeps = 1
        gravity = gravity_tensor(gravity, fluid.rank)
        velocity = fluid.velocity
        temperature = fluid.temperature
        pressure = fluid.pressure
        Yf, Yo = fluid.Yf, fluid.Yo
        wt, wkf, wko = fluid.Wt, fluid.Wkf, fluid.Wko
        Zf_min, Zf_max, Zo_min, Zo_max = get_min_max_zf_zo(fluid.eq)

        rd_yk = rd_array[20, :, :]
        rd_yk = (rd_yk - np.min(rd_yk)) / (np.max(rd_yk) - np.min(rd_yk))
        # --- update density using state equation ---
        density = (1.0 / 8.314) * pressure * (((Yf * (1 / Wf) + Yo * (1 / Wo) + (1-Yf-Yo) * (1 / Wp)) * temperature) ** (-1))

        # --- momentum equation : Advection and diffusion velocity---
        velocity = advect.semi_lagrangian(velocity, velocity, dt=dt)
        velocity = diffuse(velocity, 0.1*dt, substeps=diffusion_substeps)

        velocity += (density * gravity * fluid.buoyancy_factor * dt).at(velocity)
        # --- Effects ---
        for effect in density_effects:
            density = effect_applied(effect, density, dt)
        for effect in velocity_effects:
            velocity = effect_applied(effect, velocity, dt)

        # --- Pressure solve ---
        velocity, fluid.solve_info = divergence_free(velocity, density, fluid.domain, obstacles, self.pressure_solver, return_info=True)

        vel = velocity.data
        cx, cy = vel[1], vel[0]
        velBCy, velBCyMask = VelocityBoundary_y(velocity, rd_array, res, rd_yk, fluid.eq)
        velBCx, velBCxMask = VelocityBoundary_x(velocity)
        cy = (cy * velBCyMask) + velBCy
        cx = cx * velBCxMask
        velocity = StaggeredGrid([cy.data, cx.data], velocity.box)

        pressure_c = fluid.solve_info.get('pressure_c', None)
        pressure += pressure_c

        # --- energy equation : Advection and diffusion temperature---
        temperature = advect.semi_lagrangian(temperature, velocity, dt=dt)
        temperature = diffuse(temperature, dt*0.1, substeps=diffusion_substeps)
        temperature -= (wt * dt * ((density * cp)**(-1)))

        # --- species transport ---
        Yf = advect.semi_lagrangian(Yf, velocity, dt=dt)
        Yf = diffuse(Yf, 0.1*dt, substeps=diffusion_substeps)
        Yf += wkf * dt * (density ** -1)

        Yo = advect.semi_lagrangian(Yo, velocity, dt=dt)
        Yo = diffuse(Yo, 0.1 * dt, substeps=diffusion_substeps)
        Yo += wko * dt * (density ** -1)

        yf_mask, yo_mask = np.ones(Yf.data.shape), np.ones(Yo.data.shape)
        yf, yo = np.zeros(Yf.data.shape), np.zeros(Yo.data.shape)
        yf_mask[:, 0:1, :, :] = 0
        yf[:, 0:1, :, :] = Zf_max #(rd_yk)*(Zf_max - Zf_min) + Zf_min
        yo_mask[:, 0:1, :, :] = 0
        yo[:, 0:1, :, :] = Zo_min #Zo_max - (Zo_max - Zo_min)*rd_yk
        Yf = CenteredGrid(Yf.data*yf_mask + yf, Yf.box)
        Yo = CenteredGrid(Yo.data * yo_mask + yo, Yo.box)

        temp_mask = np.ones(temperature.data.shape)
        tempBC = np.zeros(temperature.data.shape)
        temp_mask[:, 0:1, :, :] = 0
        temp_mask[:, (res-1):res, :, :] = 0
        tempBC[:, 0:1, :, :] = 800 #np.absolute(rd_array[10,:,:])*200 + 400
        tempBC[:, (res-1):res, :, :] = 2000
        temperature = CenteredGrid(temperature.data * temp_mask + tempBC, temperature.box)

        #age_dt0 = fluid.age_dt + dt

        return fluid.copied_with(velocity=velocity, temperature= temperature, density= density, pressure = pressure, Yf = Yf, Yo = Yo, Wt = wt, Wkf = wkf, Wko = wko, age=fluid.age + dt)


SpeciesEnergy = SpEnergy()