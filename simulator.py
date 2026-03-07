class State:
    def __init__(self) -> None:
        self.bitloaders = []
        self.relays = []
        self.wires = []
        self.lights = []
        self.capacitors = []
        self.diodes = []
        self.momentary_switches = []
        self.latching_switches = []
        self.parts_by_id = {}
        self._id_counters = {
            "bitloader": 0,
            "relay": 0,
            "wire": 0,
            "light": 0,
            "capacitor": 0,
            "diode": 0,
            "momentary-switch": 0,
            "latching-switch": 0,
        }

    def _part_prefix(self, component) -> str:
        if isinstance(component, Bitloader):
            return "bitloader"
        if isinstance(component, Relay):
            return "relay"
        if isinstance(component, Wire):
            return "wire"
        if isinstance(component, Light):
            return "light"
        if isinstance(component, Capacitor):
            return "capacitor"
        if isinstance(component, Diode):
            return "diode"
        if isinstance(component, MomentarySwitch):
            return "momentary-switch"
        if isinstance(component, LatchingSwitch):
            return "latching-switch"

        raise TypeError(
            f"Unsupported component type: {type(component).__name__}"
        )

    def _assign_part_id(self, component) -> str:
        existing = getattr(component, "part_id", None)
        if existing:
            owner = self.parts_by_id.get(existing)
            if owner is not None and owner is not component:
                raise ValueError(f"Duplicate part_id detected: {existing}")

            prefix, sep, num_str = str(existing).rpartition("-")
            if sep and prefix in self._id_counters and num_str.isdigit():
                self._id_counters[prefix] = max(
                    self._id_counters[prefix], int(num_str)
                )

            self.parts_by_id[existing] = component
            return existing

        prefix = self._part_prefix(component)
        self._id_counters[prefix] += 1
        part_id = f"{prefix}-{self._id_counters[prefix]}"
        component.part_id = part_id
        self.parts_by_id[part_id] = component
        return part_id

    def get_part(self, part_id: str):
        return self.parts_by_id.get(part_id)

    def add(self, component):
        self._assign_part_id(component)

        if isinstance(
            component, Bitloader
        ) and component not in self.bitloaders:
            self.bitloaders.append(component)
        elif isinstance(component, Relay) and component not in self.relays:
            self.relays.append(component)
        elif isinstance(component, Light) and component not in self.lights:
            self.lights.append(component)
        elif (
            isinstance(component, Capacitor)
            and component not in self.capacitors
        ):
            self.capacitors.append(component)
        elif isinstance(component, Diode) and component not in self.diodes:
            self.diodes.append(component)
        elif (
            isinstance(component, MomentarySwitch)
            and component not in self.momentary_switches
        ):
            self.momentary_switches.append(component)
        elif (
            isinstance(component, LatchingSwitch)
            and component not in self.latching_switches
        ):
            self.latching_switches.append(component)
        elif isinstance(component, Wire) and component not in self.wires:
            self.wires.append(component)
        elif not isinstance(
            component,
            (
                Relay,
                Bitloader,
                Light,
                Capacitor,
                Diode,
                MomentarySwitch,
                LatchingSwitch,
                Wire,
            ),
        ):
            raise TypeError(
                f"Unsupported component type: {type(component).__name__}"
            )

        return component

    def connect(
        self,
        source,
        source_attr: str,
        target,
        target_attr: str,
        drop: float = 0.0,
    ):
        wire = Wire(
            source=source,
            source_attr=source_attr,
            target=target,
            target_attr=target_attr,
            drop=drop,
        )
        return self.add(wire)

    def process(self):
        # Run in stages so newly computed outputs can be propagated.
        for bitloader in self.bitloaders:
            bitloader.process()

        for switch in self.momentary_switches:
            switch.process()

        for switch in self.latching_switches:
            switch.process()

        for relay in self.relays:
            relay.process()

        for wire in self.wires:
            wire.process()

        for diode in self.diodes:
            diode.process()

        for wire in self.wires:
            wire.process()

        for capacitor in self.capacitors:
            capacitor.process()

        for wire in self.wires:
            wire.process()

        for light in self.lights:
            light.process()


def _gen_serialization(name, **attrs) -> str:
    attr_str = ", ".join(f"{k}={v}" for k, v in attrs.items())
    return f"{name}({attr_str});"


def _parse_bool(value, default: bool = False) -> bool:
    if value is None:
        return default
    return str(value).strip().lower() in {"1", "true", "on", "yes"}


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
            buffer=self._buffer,
            phase=self._step,
            vcc=self.vcc,
            out_voltage=self.out_v
        )


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
            coil_threshold=self.coil_threshold
        )


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
            out_voltage=self.out_v,
            norm_open=self.norm_open,
            norm_closed=self.norm_closed
        )


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
            out_voltage=self.out_v,
            norm_open=self.norm_open,
            norm_closed=self.norm_closed
        )


class Wire:
    def __init__(
        self,
        source=None,
        source_attr: str = "v",
        target=None,
        target_attr: str = "v",
        drop: float = 0.0,
    ) -> None:
        self.part_id = None
        self.v = 0.0
        self.source = source
        self.source_attr = source_attr
        self.target = target
        self.target_attr = target_attr
        self.drop = drop

    def process(self):
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
            voltage=self.v,
            source_id=self.source.part_id if self.source else None,
            source_attr=self.source_attr,
            target_id=self.target.part_id if self.target else None,
            target_attr=self.target_attr,
            drop=self.drop
        )


class Light:
    def __init__(self) -> None:
        self.part_id = None
        self.v = 0.0
        self.on_threshold = 1.8
        self.on = False

    def process(self):
        self.on = self.v >= self.on_threshold
        return self.on

    def serialize(self) -> str:
        return _gen_serialization(
            "light",
            id=self.part_id,
            voltage=self.v,
            on=self.on,
            threshold=self.on_threshold
        )


class Capacitor:
    def __init__(self) -> None:
        self.part_id = None
        self.in_v = 0.0
        self.v = 0.0
        self.max_v = 5.0
        self.charge_rate = 0.1
        self.discharge_rate = 0.1

    def process(self):
        # Charge/discharge toward input voltage at limited rates.
        target_v = max(0.0, min(self.max_v, self.in_v))

        if target_v > self.v:
            self.v = min(target_v, self.v + self.charge_rate)
        elif target_v < self.v:
            self.v = max(target_v, self.v - self.discharge_rate)

        return self.v

    def serialize(self) -> str:
        return _gen_serialization(
            "capacitor",
            id=self.part_id,
            voltage=self.v,
            in_voltage=self.in_v,
            max_voltage=self.max_v,
            charge_rate=self.charge_rate,
            discharge_rate=self.discharge_rate
        )


class Diode:
    def __init__(self) -> None:
        self.part_id = None
        self.v = 0.0
        self.out_v = 0.0
        self.forward_threshold = 0.7

    def process(self):
        if self.v >= self.forward_threshold:
            self.out_v = self.v - self.forward_threshold
        else:
            self.out_v = 0.0

        return self.out_v

    def serialize(self) -> str:
        return _gen_serialization(
            "diode",
            id=self.part_id,
            voltage=self.v,
            out_voltage=self.out_v,
            forward_threshold=self.forward_threshold
        )


class Oscillator:
    def __init__(self) -> None:
        self.part_id = None
        self.vcc = 5.0
        self.frequency = 1.0
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
            out_voltage=self.out_v
        )


class PowerSource:
    def __init__(self) -> None:
        self.part_id = None
        self.generation = 5.0
        self.out_v = 5.0

    def process(self):
        self.out_v = self.generation
        return self.out_v

    def serialize(self) -> str:
        return _gen_serialization(
            "power_source",
            id=self.part_id,
            vcc=self.generation,
            out_voltage=self.out_v
        )


if __name__ == "__main__":
    # Example: relay -> diode -> capacitor -> light
    state = State()

    relay = Relay()
    relay.vcc = 5.0
    relay.coil = 3.3

    diode = Diode()

    capacitor = Capacitor()
    capacitor.charge_rate = 1.0
    capacitor.discharge_rate = 0.5

    light = Light()
    light.on_threshold = 2.0

    state.add(relay)
    state.add(diode)
    state.add(capacitor)
    state.add(light)

    state.connect(relay, "norm_open", diode, "v")
    state.connect(diode, "out_v", capacitor, "in_v")
    state.connect(capacitor, "v", light, "v")

    print(
        "Parts:",
        relay.part_id,
        diode.part_id,
        capacitor.part_id,
        light.part_id,
    )

    print("Charging...")
    for step in range(1, 6):
        state.process()
        print(
            f"t{step}: diode_out={diode.out_v:.2f}V "
            f"cap={capacitor.v:.2f}V light_on={light.on}"
        )

    relay.coil = 0.0
    print("Discharging...")
    for step in range(6, 11):
        state.process()
        print(
            f"t{step}: diode_out={diode.out_v:.2f}V "
            f"cap={capacitor.v:.2f}V light_on={light.on}"
        )


class PC1:
    def __init__(self) -> None:
        self.state = State()
        self.file_content = ""
        self.dict_rep = []

    def load(self, filename: str):
        with open(filename, "r") as f:
            self.file_content = f.read()

        self.state = State()
        self._parse_todict()

        # Convert dictionary into a State
        # Components: relay, wire, light, capacitor, diode, switches, bitloader
        for name, attrs in self.dict_rep:
            if name == "bitloader":
                loader = Bitloader()
                loader.part_id = attrs.get("id")
                loader.speed = max(1, int(float(attrs.get("speed", 1))))
                loader.input = loader._sanitize_bits(attrs.get("input", ""))
                loader._buffer = loader._sanitize_bits(attrs.get("buffer", ""))
                loader._step = max(0, int(float(attrs.get("phase", 0))))
                loader.vcc = float(attrs.get("vcc", 5.0))
                loader.out_v = float(attrs.get("out_voltage", 0.0))
                self.state.add(loader)
            elif name == "relay":
                relay = Relay()
                relay.part_id = attrs.get("id")
                relay.coil = float(attrs.get("coil", 0.0))
                relay.vcc = float(attrs.get("vcc", 0.0))
                relay.norm_open = float(attrs.get("norm_open", 0.0))
                relay.norm_closed = float(attrs.get("norm_closed", 0.0))
                relay.coil_threshold = float(attrs.get("coil_threshold", 2.0))
                self.state.add(relay)
            elif name == "light":
                light = Light()
                light.part_id = attrs.get("id")
                light.v = float(attrs.get("voltage", 0.0))
                light.on_threshold = float(attrs.get("threshold", 1.8))
                light.on = _parse_bool(attrs.get("on"), False)
                self.state.add(light)
            elif name == "capacitor":
                cap = Capacitor()
                cap.part_id = attrs.get("id")
                cap.v = float(attrs.get("voltage", 0.0))
                cap.in_v = float(attrs.get("in_voltage", 0.0))
                cap.max_v = float(attrs.get("max_voltage", 5.0))
                cap.charge_rate = float(attrs.get("charge_rate", 0.1))
                cap.discharge_rate = float(attrs.get("discharge_rate", 0.1))
                self.state.add(cap)
            elif name == "diode":
                diode = Diode()
                diode.part_id = attrs.get("id")
                diode.v = float(attrs.get("voltage", 0.0))
                diode.out_v = float(attrs.get("out_voltage", 0.0))
                diode.forward_threshold = float(
                    attrs.get("forward_threshold", 0.7)
                )
                self.state.add(diode)
            elif name == "momentary_switch":
                switch = MomentarySwitch()
                switch.part_id = attrs.get("id")
                switch.vcc = float(attrs.get("vcc", 5.0))
                switch.pressed = _parse_bool(attrs.get("pressed"), False)
                switch.out_v = float(attrs.get("out_voltage", 0.0))
                switch.norm_open = float(attrs.get("norm_open", 0.0))
                switch.norm_closed = float(
                    attrs.get("norm_closed", switch.vcc)
                )
                self.state.add(switch)
            elif name == "latching_switch":
                switch = LatchingSwitch()
                switch.part_id = attrs.get("id")
                switch.vcc = float(attrs.get("vcc", 5.0))
                switch.latched = _parse_bool(attrs.get("latched"), False)
                switch.out_v = float(attrs.get("out_voltage", 0.0))
                switch.norm_open = float(attrs.get("norm_open", 0.0))
                switch.norm_closed = float(
                    attrs.get("norm_closed", switch.vcc)
                )
                self.state.add(switch)

        # Create wires after all endpoint parts exist.
        for name, attrs in self.dict_rep:
            if name == "wire":
                source = None
                target = None

                source_id = attrs.get("source_id")
                target_id = attrs.get("target_id")
                if source_id:
                    source = self.state.get_part(source_id)
                if target_id:
                    target = self.state.get_part(target_id)

                wire = Wire(
                    source=source,
                    source_attr=attrs.get("source_attr", "v"),
                    target=target,
                    target_attr=attrs.get("target_attr", "v"),
                    drop=float(attrs.get("drop", 0.0)),
                )
                wire.part_id = attrs.get("id")
                wire.v = float(attrs.get("voltage", 0.0))
                self.state.add(wire)

    def _parse_todict(self):
        self.dict_rep = []
        clean = self.file_content.strip()
        statements = clean.split(";")
        for stm in statements:
            if not stm.strip():
                continue
            name, args_str = stm.split("(", 1)
            args_str = args_str.rsplit(")", 1)[0]
            args = {}
            for arg in args_str.split(","):
                if not arg.strip():
                    continue
                key, value = arg.split("=", 1)
                args[key.strip()] = value.strip()
            self.dict_rep.append((name.strip(), args))

    def save(self, filename: str):
        lines = []
        for loader in self.state.bitloaders:
            lines.append(loader.serialize())
        for relay in self.state.relays:
            lines.append(relay.serialize())
        for switch in self.state.momentary_switches:
            lines.append(switch.serialize())
        for switch in self.state.latching_switches:
            lines.append(switch.serialize())
        for light in self.state.lights:
            lines.append(light.serialize())
        for cap in self.state.capacitors:
            lines.append(cap.serialize())
        for diode in self.state.diodes:
            lines.append(diode.serialize())
        for wire in self.state.wires:
            lines.append(wire.serialize())

        self.file_content = "\n".join(lines)

        with open(filename, "w") as f:
            f.write(self.file_content)
