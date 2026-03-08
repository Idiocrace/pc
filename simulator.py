class State:
    def __init__(self) -> None:
        raise DeprecationWarning("State is deprecated. Please use Sim instead")


def _gen_serialization(_, **attrs) -> str:
    attr_str = ", ".join(f"{k}={v}" for k, v in attrs.items())
    return f"{_}({attr_str});"


def _parse_bool(value, default: bool = False) -> bool:
    if value is None:
        return default
    return str(value).strip().lower() in {"1", "true", "on", "yes"}


components = {}


# Component decorator
def Component(serial_name=None):
    def decorator(cls):
        name = serial_name if serial_name else cls.__name__.lower()
        components[name] = cls
        return cls

    # If called without arguments as a bare decorator: @Component
    if callable(serial_name):
        cls = serial_name
        components[cls.__name__.lower()] = cls
        return cls

    return decorator


@Component("bitloader")
class Bitloader:
    def __init__(self) -> None:
        self.part_id = None
        self.speed = 1
        self.input = ""
        self._buffer = ""
        self._step = 0
        self.vcc = 5.0
        self.out_v = 0.0

    @staticmethod
    def _sanitize_bits(bits: str) -> str:
        return "".join(ch for ch in str(bits) if ch in {"0", "1"})

    def enqueue(self, bits: str) -> None:
        clean = self._sanitize_bits(bits)
        if not clean:
            return
        self._buffer += clean

    def process(self):
        if self.input != "":
            self.enqueue(self.input)
            self.input = ""
        if self._buffer:
            self._step += 1
            speed = max(1, int(self.speed))
            if self._step >= speed:
                self._step = 0
                bit = self._buffer[0]
                self._buffer = self._buffer[1:]
                self.out_v = self.vcc if bit == "1" else 0.0

    def serialize(self) -> str:
        return _gen_serialization(
            "bitloader",
            id=self.part_id,
            speed=self.speed,
            input=self.input,
            _buffer=self._buffer,
            _step=self._step,
            vcc=self.vcc,
            out_v=self.out_v,
        )


@Component("relay")
class Relay:
    def __init__(self) -> None:
        self.part_id = None
        self.coil = 0.0
        self.vcc = 0.0
        self.norm_open = 0.0
        self.norm_closed = 0.0
        self.coil_threshold = 2.0

    def process(self):
        if self.coil >= self.coil_threshold:
            self.norm_open = self.vcc
            self.norm_closed = 0.0
        else:
            self.norm_open = 0.0
            self.norm_closed = self.vcc

    def serialize(self) -> str:
        return _gen_serialization(
            "relay",
            id=self.part_id,
            coil=self.coil,
            vcc=self.vcc,
            norm_open=self.norm_open,
            norm_closed=self.norm_closed,
            coil_threshold=self.coil_threshold,
        )


@Component("momentary_switch")
class MomentarySwitch:
    def __init__(self) -> None:
        self.part_id = None
        self.vcc = 5.0
        self.pressed = False
        self.out_v = 0.0
        self.norm_open = 0.0
        self.norm_closed = self.vcc

    def process(self):
        self.norm_open = self.vcc if self.pressed else 0.0
        self.norm_closed = 0.0 if self.pressed else self.vcc
        self.out_v = self.norm_open
        return self.out_v

    def press(self):
        self.pressed = True

    def release(self):
        self.pressed = False

    def serialize(self) -> str:
        return _gen_serialization(
            "momentary_switch",
            id=self.part_id,
            vcc=self.vcc,
            pressed=self.pressed,
            out_v=self.out_v,
            norm_open=self.norm_open,
            norm_closed=self.norm_closed,
        )


@Component("latching_switch")
class LatchingSwitch:
    def __init__(self) -> None:
        self.part_id = None
        self.vcc = 5.0
        self.latched = False
        self.out_v = 0.0
        self.norm_open = 0.0
        self.norm_closed = self.vcc

    def process(self):
        self.norm_open = self.vcc if self.latched else 0.0
        self.norm_closed = 0.0 if self.latched else self.vcc
        self.out_v = self.norm_open
        return self.out_v

    def toggle(self):
        self.latched = not self.latched

    def serialize(self) -> str:
        return _gen_serialization(
            "latching_switch",
            id=self.part_id,
            vcc=self.vcc,
            latched=self.latched,
            out_v=self.out_v,
            norm_open=self.norm_open,
            norm_closed=self.norm_closed,
        )


# Technically not a component
class Wire:
    def __init__(
        self,
        source=None,
        source_attr: str = "v",
        target=None,
        target_attr: str = "v",
        drop: float = 0.0,
    ) -> None:
        self.part_id: str | None = None
        self.v = 0.0
        self.enabled = True
        self.source = source
        self.source_attr = source_attr
        self.target = target
        self.target_attr = target_attr
        self.drop = drop

    def process(self):
        if not self.enabled:
            self.v = 0.0
            if self.target is not None:
                setattr(self.target, self.target_attr, 0.0)
            return 0.0

        if self.source is not None:
            self.v = float(getattr(self.source, self.source_attr, 0.0))

        out_v = max(0.0, self.v - self.drop)

        if self.target is not None:
            setattr(self.target, self.target_attr, out_v)

        return out_v

    def serialize(self) -> str:
        return _gen_serialization(
            "wire",
            id=self.part_id,
            v=self.v,
            source_id=self.source.part_id if self.source else None,
            source_attr=self.source_attr,
            target_id=self.target.part_id if self.target else None,
            target_attr=self.target_attr,
            drop=self.drop,
        )


@Component("light")
class Light:
    def __init__(self) -> None:
        self.part_id = None
        self.is_consumer = True
        self.vcc = 0.0
        self.gnd = 0.0
        self.on_threshold = 1.8
        self.on = False

    def process(self):
        self.on = self.vcc >= self.on_threshold
        return self.on

    def serialize(self) -> str:
        return _gen_serialization(
            "light",
            id=self.part_id,
            vcc=self.vcc,
            on=self.on,
            on_threshold=self.on_threshold,
        )


@Component("capacitor")
class Capacitor:
    def __init__(self) -> None:
        self.part_id = None
        self.is_storage = True
        self.vcc = 0.0
        self.gnd = 0.0
        self.v = 0.0
        self.max_v = 5.0
        self.charge_rate = 0.1
        self.discharge_rate = 0.1

    def process(self):
        # Charge/discharge toward input voltage at limited rates.
        target_v = max(0.0, min(self.max_v, self.vcc))

        if target_v > self.v:
            self.v = min(target_v, self.v + self.charge_rate)
        elif target_v < self.v:
            self.v = max(target_v, self.v - self.discharge_rate)

        return self.v

    def serialize(self) -> str:
        return _gen_serialization(
            "capacitor",
            id=self.part_id,
            v=self.v,
            vcc=self.vcc,
            max_v=self.max_v,
            charge_rate=self.charge_rate,
            discharge_rate=self.discharge_rate,
        )


@Component("diode")
class Diode:
    def __init__(self) -> None:
        self.part_id = None
        self.vcc = 0.0
        self.out_v = 0.0
        self.drain_rate = 1.0
        self.forward_threshold = 0.7
        self.backward_threshold = 5

    def process(self):
        if self.vcc >= self.forward_threshold:
            self.out_v = self.vcc - self.forward_threshold
        elif self.out_v >= self.backward_threshold:
            self.vcc = self.out_v
            self.out_v -= self.drain_rate * self.out_v
            if self.out_v < 0.01:
                self.out_v = 0
        return self.out_v

    def serialize(self) -> str:
        return _gen_serialization(
            "diode",
            id=self.part_id,
            vcc=self.vcc,
            out_v=self.out_v,
            forward_threshold=self.forward_threshold,
            backward_threshold=self.backward_threshold,
            drain_rate=self.drain_rate,
        )


@Component("oscillator")
class Oscillator:
    def __init__(self) -> None:
        self.part_id = None
        self.vcc = 0.0
        self.frequency = 1.0  # Every f steps, swap state
        self.out_v = 0.0

    def process(self):
        if self.frequency == self.vcc:
            self.out_v = 0.0
        else:
            self.out_v = self.vcc

    def serialize(self) -> str:
        return _gen_serialization(
            "oscillator",
            id=self.part_id,
            vcc=self.vcc,
            frequency=self.frequency,
            out_v=self.out_v,
        )


@Component("supply")
class Supply:
    def __init__(self) -> None:
        self.part_id = None
        self.generation = 5.0
        self.over_protection_rate = 0.1
        self.v_out = 0.0

    def process(self):
        if self.v_out <= self.generation:
            self.v_out += self.generation
        elif self.v_out > self.generation:
            # OVERLOAD!!!
            self.v_out -= self.over_protection_rate
            if self.v_out < 0:
                self.v_out = 0
        return self.v_out

    def serialize(self) -> str:
        return _gen_serialization(
            "supply",
            id=self.part_id,
            generation=self.generation,
            over_protection_rate=self.over_protection_rate,
            v_out=self.v_out,
        )


@Component("drain")
class Drain:
    def __init__(self) -> None:
        self.part_id = None
        self.is_sink = True
        self.is_consumer = True
        self.drain = 5.0
        self.vcc = 0.0

    def process(self):
        self.vcc = max(0.0, self.vcc - self.drain)
        return self.vcc

    def serialize(self) -> str:
        return _gen_serialization(
            "drain", id=self.part_id, drain=self.drain, vcc=self.vcc
        )


@Component("ground")
class Ground:
    def __init__(self) -> None:
        self.part_id = None
        self.is_sink = True
        self.vcc = 0.0

    def process(self):
        self.vcc = 0.0
        return self.vcc

    def serialize(self) -> str:
        return _gen_serialization("ground", id=self.part_id, vcc=self.vcc)


class PC1:
    """DEPRECATED: This class is deprecated. Use Sim instead"""

    def __init__(self):
        raise DeprecationWarning("PC1 is deprecated. Please use Sim instead")


class Sim:
    def __init__(self, version):
        self.name = ""
        self.version = version
        self.components = {}
        self.curr_step = 0

    def _assign_part_id(self, part_id: str | None, component_name: str) -> str:
        if part_id:
            return part_id
        idx = 1
        while f"{component_name}-{idx}" in self.components:
            idx += 1
        return f"{component_name}-{idx}"

    def add_component(self, component_name: str, **attrs):
        if component_name not in components:
            raise TypeError(f"Unknown component type: {component_name}")

        comp = components[component_name]()
        for k, v in attrs.items():
            if k == "id":
                continue
            if not hasattr(comp, k):
                raise AttributeError(
                    f"Component '{component_name}' has no attribute '{k}'."
                )
            current = getattr(comp, k)
            if isinstance(current, bool):
                setattr(comp, k, _parse_bool(v))
            else:
                setattr(comp, k, type(current)(v))

        comp.part_id = self._assign_part_id(attrs.get("id"), component_name)
        self.components[comp.part_id] = comp
        return comp

    def connect(
        self,
        source_id: str,
        source_attr: str,
        target_id: str,
        target_attr: str,
        drop: float = 0.0,
        wire_id: str | None = None,
    ):
        if source_id not in self.components or target_id not in self.components:
            raise ValueError("Both source_id and target_id must exist before connect.")

        wire = Wire(
            source=self.components[source_id],
            source_attr=source_attr,
            target=self.components[target_id],
            target_attr=target_attr,
            drop=float(drop),
        )
        wire.part_id = self._assign_part_id(wire_id, "wire")
        self.components[wire.part_id] = wire
        return wire

    def _is_wire(self, comp):
        return isinstance(comp, Wire)

    def _is_sink(self, comp):
        return bool(getattr(comp, "is_sink", False))

    def _is_storage_or_consumer(self, comp):
        return bool(
            getattr(comp, "is_storage", False) or getattr(comp, "is_consumer", False)
        )

    def _next_components(self, comp):
        for maybe_wire in self.components.values():
            if not self._is_wire(maybe_wire):
                continue
            if maybe_wire.source is comp and maybe_wire.target is not None:
                yield maybe_wire.target

    def _path_has_sink_and_load(self, start_comp):
        stack = [(start_comp, self._is_storage_or_consumer(start_comp))]
        visited = set()

        while stack:
            comp, seen_load = stack.pop()
            key = (id(comp), seen_load)
            if key in visited:
                continue
            visited.add(key)

            if self._is_sink(comp) and seen_load:
                return True

            for nxt in self._next_components(comp):
                stack.append((nxt, seen_load or self._is_storage_or_consumer(nxt)))

        return False

    def _update_wire_flow_permissions(self):
        has_any_sink = any(
            self._is_sink(comp)
            for comp in self.components.values()
            if not self._is_wire(comp)
        )

        for comp in self.components.values():
            if not self._is_wire(comp):
                continue

            # No drain/ground means no current flow.
            if not has_any_sink:
                comp.enabled = False
                continue

            if comp.source is None or comp.target is None:
                comp.enabled = False
                continue

            comp.enabled = self._path_has_sink_and_load(comp.target)

    def load_sim_state(self, path):
        with open(path, "r") as f:
            tmp_raw_file_content = f.read()
            tmp_file_content = tmp_raw_file_content.strip()
            # Before tokenizing and parsing, check all lines to see if its a comment
            tmp_file_content = "\n".join(
                line
                for line in tmp_file_content.splitlines()
                if not line.strip().startswith("#")
            )
            tmp_tokens = tmp_file_content.split(";")
            tmp_raw_components = []
            for token in tmp_tokens:
                token = token.strip()
                if not token:
                    continue
                tmp_name_args = token.strip(")").split("(", 1)
                tmp_name = tmp_name_args[0]
                tmp_raw_args = tmp_name_args[1].split(",")
                tmp_args = {}
                for arg in tmp_raw_args:
                    tmp_kv = arg.split("=", 1)
                    if len(tmp_kv) == 2:
                        tmp_k, tmp_v = tmp_kv
                        tmp_args[tmp_k.strip()] = tmp_v.strip()
                tmp_raw_components.append((tmp_name, tmp_args))

            meta_args = None
            for comp_name, comp_args in tmp_raw_components:
                if comp_name == "@meta":
                    meta_args = comp_args
                    break

            if meta_args is None:
                raise SyntaxError("Sim-state files must contain an '@meta' dataset.")

            tmp_split_version = self.version.split(".")
            tmp_file_split_version = meta_args["version"].split(".")
            if tmp_split_version[0] != tmp_file_split_version[0]:
                raise SyntaxError(
                    f"Sim-state major version {tmp_file_split_version[0]} does not"
                    f" match Sim version {tmp_split_version[0]}."
                )
            self.name = meta_args["name"]

        self.components = {}

        # Get to component creation
        for comp_name, comp_args in tmp_raw_components:
            if comp_name == "@meta" or comp_name == "wire":
                continue

            if comp_name not in components:
                raise TypeError(
                    f"Component type {comp_name} does not exist nor is special."
                )

            comp_cls = components[comp_name]
            comp_instance = comp_cls()
            for arg_k, arg_v in comp_args.items():
                if arg_k in {"id", "source_id", "target_id"}:
                    continue
                if hasattr(comp_instance, arg_k):
                    attr_type = type(getattr(comp_instance, arg_k))
                    try:
                        if attr_type is bool:
                            setattr(comp_instance, arg_k, _parse_bool(arg_v))
                        else:
                            setattr(comp_instance, arg_k, attr_type(arg_v))
                    except ValueError:
                        raise ValueError(
                            f"Invalid argument value for component '{comp_name}'"
                            f" attribute '{arg_k}': '{arg_v}'"
                        )
                else:
                    raise AttributeError(
                        f"Component '{comp_name}' has no attribute '{arg_k}'."
                    )

            comp_instance.part_id = comp_args.get("id")
            if not comp_instance.part_id:
                raise ValueError(f"Component '{comp_name}' must define a non-empty id.")
            self.components[comp_instance.part_id] = comp_instance

        # After component creation, we need to register wire connections
        # This is done separately because wires technically arent components internally
        for comp_name, comp_args in tmp_raw_components:
            if comp_name == "wire":
                source_id = comp_args["source_id"]
                target_id = comp_args["target_id"]
                if source_id not in self.components or target_id not in self.components:
                    raise ValueError(
                        f"Invalid wire connection: source id {source_id} or target"
                        f" id {target_id} does not exist."
                    )
                source_comp = self.components[source_id]
                target_comp = self.components[target_id]
                wire_instance = Wire(
                    source=source_comp,
                    source_attr=comp_args["source_attr"],
                    target=target_comp,
                    target_attr=comp_args["target_attr"],
                    drop=float(comp_args["drop"]),
                )
                wire_instance.part_id = comp_args.get("id")
                if not wire_instance.part_id:
                    raise ValueError("Wire must define a non-empty id.")
                self.components[wire_instance.part_id] = wire_instance

    def save_sim_state(self, path):
        with open(path, "w") as f:
            f.write(
                _gen_serialization("@meta", name=self.name, version=self.version) + "\n"
            )
            for comp in self.components.values():
                f.write(comp.serialize() + "\n")

    def step(self):
        for comp in self.components.values():
            if not self._is_wire(comp):
                comp.process()

        self._update_wire_flow_permissions()

        for comp in self.components.values():
            if self._is_wire(comp):
                comp.process()

        for comp in self.components.values():
            if not self._is_wire(comp):
                comp.process()

        self.curr_step += 1

    def reset(self):
        self.curr_step = 0
        original_items = list(self.components.items())
        self.components = {}
        for part_id, comp in original_items:
            comp.__init__()
            comp.part_id = part_id
            self.components[part_id] = comp
