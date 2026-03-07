from __future__ import annotations

import argparse
import shlex
import sys
import time
from pathlib import Path

import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from simulator import Bitloader, LatchingSwitch, MomentarySwitch, PC1, Relay


def _to_value(raw: str):
    lowered = raw.strip().lower()
    if lowered in {"true", "on", "yes", "1"}:
        return True
    if lowered in {"false", "off", "no", "0"}:
        return False

    try:
        return float(raw)
    except ValueError:
        return raw


class SimulatorCLI:
    def __init__(self) -> None:
        self.pc = PC1()
        self.loaded_file: Path | None = None
        self.tick = 0

    def load(self, filename: str) -> None:
        path = Path(filename)
        if not path.exists():
            raise FileNotFoundError(f"File not found: {filename}")

        self.pc.load(str(path))
        self.loaded_file = path
        self.tick = 0
        print(f"Loaded {path}.")
        print(
            "Parts: "
            f"{len(self.pc.state.bitloaders)} bitloaders, "
            f"{len(self.pc.state.relays)} relays, "
            f"{len(self.pc.state.diodes)} diodes, "
            f"{len(self.pc.state.capacitors)} capacitors, "
            f"{len(self.pc.state.lights)} lights, "
            f"{len(self.pc.state.momentary_switches)} momentary switches, "
            f"{len(self.pc.state.latching_switches)} latching switches, "
            f"{len(self.pc.state.wires)} wires"
        )

    def save(self, filename: str | None = None) -> None:
        if filename:
            out = Path(filename)
        elif self.loaded_file:
            out = self.loaded_file
        else:
            raise ValueError("No target file specified.")

        self.pc.save(str(out))
        print(f"Saved {out}.")

    def step(self, count: int = 1, verbose: bool = True) -> None:
        if count < 1:
            raise ValueError("Step count must be >= 1")

        for _ in range(count):
            self.pc.state.process()
            self.tick += 1

        if verbose:
            print(f"Advanced {count} step(s). Tick={self.tick}")
            self.show_lights()

    def run(self, count: int, delay_s: float = 0.0) -> None:
        if count < 1:
            raise ValueError("Run count must be >= 1")
        if delay_s < 0:
            raise ValueError("Delay must be >= 0")

        for _ in range(count):
            self.step(1, verbose=False)
            print(f"Tick={self.tick}", end=" ")
            self.show_lights(prefix="")
            if delay_s:
                time.sleep(delay_s)

    def show_lights(self, prefix: str = "Lights: ") -> None:
        if not self.pc.state.lights:
            print("No lights present.")
            return

        states = []
        for light in self.pc.state.lights:
            states.append(
                f"{light.part_id}={'ON' if light.on else 'off'}({light.v:.2f}V)"
            )
        print(prefix + " ".join(states))

    def status(self) -> None:
        print(f"Tick: {self.tick}")

        print("Bitloaders:")
        for loader in self.pc.state.bitloaders:
            print(
                f"  {loader.part_id}: speed={loader.speed} phase={loader._step} "
                f"queue='{loader._buffer}' out={loader.out_v:.2f}V"
            )

        print("Momentary switches:")
        for switch in self.pc.state.momentary_switches:
            print(
                f"  {switch.part_id}: pressed={switch.pressed} "
                f"out={switch.out_v:.2f}V vcc={switch.vcc:.2f}V"
            )

        print("Latching switches:")
        for switch in self.pc.state.latching_switches:
            print(
                f"  {switch.part_id}: latched={switch.latched} "
                f"out={switch.out_v:.2f}V vcc={switch.vcc:.2f}V"
            )

        print("Relays:")
        for relay in self.pc.state.relays:
            print(
                f"  {relay.part_id}: coil={relay.coil:.2f}V vcc={relay.vcc:.2f}V "
                f"NO={relay.norm_open:.2f}V NC={relay.norm_closed:.2f}V"
            )

        print("Diodes:")
        for diode in self.pc.state.diodes:
            print(
                f"  {diode.part_id}: in={diode.v:.2f}V out={diode.out_v:.2f}V "
                f"th={diode.forward_threshold:.2f}V"
            )

        print("Capacitors:")
        for cap in self.pc.state.capacitors:
            print(
                f"  {cap.part_id}: in={cap.in_v:.2f}V v={cap.v:.2f}V "
                f"max={cap.max_v:.2f}V"
            )

        self.show_lights()

    def list_parts(self, kind: str = "all") -> None:
        kinds = {
            "bitloader": self.pc.state.bitloaders,
            "relay": self.pc.state.relays,
            "wire": self.pc.state.wires,
            "light": self.pc.state.lights,
            "capacitor": self.pc.state.capacitors,
            "diode": self.pc.state.diodes,
            "momentary_switch": self.pc.state.momentary_switches,
            "latching_switch": self.pc.state.latching_switches,
        }

        if kind == "all":
            for key, items in kinds.items():
                print(f"{key}s: {[p.part_id for p in items]}")
            return

        if kind not in kinds:
            raise ValueError(
                "kind must be one of: all bitloader relay wire light "
                "capacitor diode momentary_switch latching_switch"
            )

        print([p.part_id for p in kinds[kind]])

    def show_part(self, part_id: str) -> None:
        part = self.pc.state.get_part(part_id)
        if part is None:
            raise ValueError(f"Unknown part id: {part_id}")

        attrs = {
            key: value
            for key, value in vars(part).items()
            if not key.startswith("_")
        }
        print(f"{part_id}: {attrs}")

    def set_attr(self, part_id: str, attr: str, raw_value: str) -> None:
        part = self.pc.state.get_part(part_id)
        if part is None:
            raise ValueError(f"Unknown part id: {part_id}")
        if not hasattr(part, attr):
            raise ValueError(f"{part_id} has no attribute '{attr}'")

        current = getattr(part, attr)
        value = _to_value(raw_value)

        if isinstance(current, float) and isinstance(value, str):
            raise ValueError(f"{part_id}.{attr} expects a numeric value")
        if isinstance(current, bool):
            value = bool(value)
        elif isinstance(current, float):
            value = float(value)

        setattr(part, attr, value)
        print(f"Set {part_id}.{attr} = {value}")

    def set_coil(self, relay_id: str, value: float) -> None:
        part = self.pc.state.get_part(relay_id)
        if not isinstance(part, Relay):
            raise ValueError(f"{relay_id} is not a relay")

        part.coil = float(value)
        print(f"Set {relay_id}.coil = {part.coil}")

    def pulse(self, relay_id: str, value: float, steps: int) -> None:
        part = self.pc.state.get_part(relay_id)
        if not isinstance(part, Relay):
            raise ValueError(f"{relay_id} is not a relay")
        if steps < 1:
            raise ValueError("steps must be >= 1")

        prev = part.coil
        part.coil = float(value)
        self.step(steps, verbose=False)
        part.coil = prev
        print(
            f"Pulsed {relay_id}.coil={value} for {steps} step(s), restored {prev}"
        )
        self.show_lights()

    def set_momentary(self, switch_id: str, pressed: bool) -> None:
        part = self.pc.state.get_part(switch_id)
        if not isinstance(part, MomentarySwitch):
            raise ValueError(f"{switch_id} is not a momentary switch")
        part.pressed = bool(pressed)
        print(f"Set {switch_id}.pressed = {part.pressed}")

    def set_latch(self, switch_id: str, latched: bool) -> None:
        part = self.pc.state.get_part(switch_id)
        if not isinstance(part, LatchingSwitch):
            raise ValueError(f"{switch_id} is not a latching switch")
        part.latched = bool(latched)
        print(f"Set {switch_id}.latched = {part.latched}")

    def toggle_latch(self, switch_id: str) -> None:
        part = self.pc.state.get_part(switch_id)
        if not isinstance(part, LatchingSwitch):
            raise ValueError(f"{switch_id} is not a latching switch")
        part.toggle()
        print(f"Toggled {switch_id}.latched -> {part.latched}")

    def queue_bits(self, loader_id: str, bits: str) -> None:
        part = self.pc.state.get_part(loader_id)
        if not isinstance(part, Bitloader):
            raise ValueError(f"{loader_id} is not a bitloader")
        clean = part._sanitize_bits(bits)
        if not clean:
            raise ValueError("Bits must contain at least one 0 or 1")
        part.enqueue(clean)
        print(f"Queued {len(clean)} bits into {loader_id}: {clean}")

    def set_bitloader_speed(self, loader_id: str, speed: int) -> None:
        part = self.pc.state.get_part(loader_id)
        if not isinstance(part, Bitloader):
            raise ValueError(f"{loader_id} is not a bitloader")
        part.speed = max(1, int(speed))
        print(f"Set {loader_id}.speed = {part.speed}")

    def clear_bitloader(self, loader_id: str) -> None:
        part = self.pc.state.get_part(loader_id)
        if not isinstance(part, Bitloader):
            raise ValueError(f"{loader_id} is not a bitloader")
        part.input = ""
        part._buffer = ""
        part._step = 0
        part.out_v = 0.0
        print(f"Cleared {loader_id} queue")

    def help(self) -> None:
        print("Commands:")
        print("  help")
        print("  load <file.pc1>")
        print("  save [file.pc1]")
        print("  status")
        print("  lights")
        print(
            "  list [all|bitloader|relay|wire|light|capacitor|diode|"
            "momentary_switch|latching_switch]"
        )
        print("  show <part_id>")
        print("  step [count]")
        print("  run <count> [delay_seconds]")
        print("  queue <bitloader_id> <bit-string>")
        print("  bspeed <bitloader_id> <ticks-per-bit>")
        print("  bclear <bitloader_id>")
        print("  coil <relay_id> <voltage>")
        print("  pulse <relay_id> <voltage> <steps>")
        print("  press <momentary_switch_id>")
        print("  release <momentary_switch_id>")
        print("  latch <latching_switch_id> <on|off>")
        print("  toggle <latching_switch_id>")
        print("  set <part_id> <attr> <value>")
        print("  quit")

    def repl(self) -> None:
        print("Relay simulator CLI. Type 'help' for commands.")

        while True:
            try:
                line = input("pc> ").strip()
            except (EOFError, KeyboardInterrupt):
                print("\nExiting.")
                return

            if not line:
                continue

            try:
                parts = shlex.split(line)
                cmd = parts[0].lower()
                args = parts[1:]

                if cmd in {"quit", "exit"}:
                    print("Exiting.")
                    return
                if cmd == "help":
                    self.help()
                elif cmd == "load":
                    self.load(args[0])
                elif cmd == "save":
                    self.save(args[0] if args else None)
                elif cmd == "status":
                    self.status()
                elif cmd == "lights":
                    self.show_lights()
                elif cmd == "list":
                    self.list_parts(args[0] if args else "all")
                elif cmd == "show":
                    self.show_part(args[0])
                elif cmd == "step":
                    self.step(int(args[0]) if args else 1)
                elif cmd == "run":
                    count = int(args[0])
                    delay = float(args[1]) if len(args) > 1 else 0.0
                    self.run(count, delay)
                elif cmd == "queue":
                    self.queue_bits(args[0], args[1])
                elif cmd == "bspeed":
                    self.set_bitloader_speed(args[0], int(args[1]))
                elif cmd == "bclear":
                    self.clear_bitloader(args[0])
                elif cmd == "coil":
                    self.set_coil(args[0], float(args[1]))
                elif cmd == "pulse":
                    self.pulse(args[0], float(args[1]), int(args[2]))
                elif cmd == "press":
                    self.set_momentary(args[0], True)
                elif cmd == "release":
                    self.set_momentary(args[0], False)
                elif cmd == "latch":
                    self.set_latch(args[0], bool(_to_value(args[1])))
                elif cmd == "toggle":
                    self.toggle_latch(args[0])
                elif cmd == "set":
                    self.set_attr(args[0], args[1], args[2])
                else:
                    print(f"Unknown command: {cmd}")
            except IndexError:
                print("Missing command arguments. Type 'help'.")
            except Exception as exc:
                print(f"Error: {exc}")


class SimulatorGUI:
    def __init__(self, cli: SimulatorCLI, initial_file: str) -> None:
        self.cli = cli
        self.running = False
        self.relay_update_guard = False

        self.root = tk.Tk()
        self.root.title("Relay Computer Simulator")
        self.root.geometry("980x700")

        self.file_var = tk.StringVar(value=initial_file)
        self.tick_var = tk.StringVar(value="Tick: 0")
        self.run_button_var = tk.StringVar(value="Run")
        self.interval_var = tk.IntVar(value=150)

        self.light_widgets = {}
        self.bitloader_input_vars = {}
        self.bitloader_speed_vars = {}
        self.bitloader_status_vars = {}
        self.momentary_state_vars = {}
        self.latch_vars = {}
        self.relay_coil_vars = {}

        self._build_layout()
        self.load_file(initial_file, show_error=False)

    def _build_layout(self) -> None:
        top = ttk.Frame(self.root, padding=8)
        top.pack(fill="x")

        ttk.Label(top, text="Module file:").pack(side="left")
        ttk.Entry(top, textvariable=self.file_var, width=55).pack(
            side="left", padx=6, fill="x", expand=True
        )
        ttk.Button(top, text="Browse", command=self.browse_file).pack(side="left")
        ttk.Button(top, text="Load", command=self.load_from_entry).pack(
            side="left", padx=4
        )
        ttk.Button(top, text="Save", command=self.save_current).pack(side="left")

        controls = ttk.Frame(self.root, padding=8)
        controls.pack(fill="x")

        ttk.Label(controls, textvariable=self.tick_var).pack(side="left", padx=6)
        ttk.Button(controls, text="Step 1", command=lambda: self.step_n(1)).pack(
            side="left", padx=4
        )
        ttk.Button(controls, text="Step 5", command=lambda: self.step_n(5)).pack(
            side="left", padx=4
        )
        ttk.Button(controls, text="Step 20", command=lambda: self.step_n(20)).pack(
            side="left", padx=4
        )
        ttk.Button(
            controls,
            textvariable=self.run_button_var,
            command=self.toggle_running,
        ).pack(side="left", padx=8)
        ttk.Label(controls, text="Interval ms:").pack(side="left", padx=(20, 4))
        ttk.Spinbox(
            controls,
            from_=20,
            to=2000,
            increment=10,
            textvariable=self.interval_var,
            width=8,
        ).pack(side="left")

        main = ttk.Panedwindow(self.root, orient="horizontal")
        main.pack(fill="both", expand=True, padx=8, pady=(0, 8))

        left = ttk.Frame(main, padding=4)
        right = ttk.Frame(main, padding=4)
        main.add(left, weight=1)
        main.add(right, weight=1)

        self.lights_frame = ttk.LabelFrame(left, text="Lights", padding=8)
        self.lights_frame.pack(fill="x", pady=4)

        self.bitloaders_frame = ttk.LabelFrame(left, text="Bitloaders", padding=8)
        self.bitloaders_frame.pack(fill="x", pady=4)

        self.switches_frame = ttk.LabelFrame(left, text="Switches", padding=8)
        self.switches_frame.pack(fill="x", pady=4)

        self.relays_frame = ttk.LabelFrame(left, text="Relay Coil Controls", padding=8)
        self.relays_frame.pack(fill="x", pady=4)

        self.status_frame = ttk.LabelFrame(right, text="Status", padding=8)
        self.status_frame.pack(fill="both", expand=True, pady=4)
        self.status_text = tk.Text(self.status_frame, wrap="none", height=35)
        self.status_text.pack(fill="both", expand=True)
        self.status_text.configure(state="disabled")

    def browse_file(self) -> None:
        chosen = filedialog.askopenfilename(
            title="Open .pc1 module",
            filetypes=[("PC1 module", "*.pc1"), ("All files", "*.*")],
        )
        if chosen:
            self.file_var.set(chosen)
            self.load_file(chosen)

    def load_from_entry(self) -> None:
        self.load_file(self.file_var.get().strip())

    def load_file(self, filename: str, show_error: bool = True) -> None:
        try:
            self.cli.load(filename)
            self.file_var.set(filename)
            self._rebuild_dynamic_panels()
            self.refresh_view()
        except Exception as exc:
            if show_error:
                messagebox.showerror("Load failed", str(exc))
            else:
                raise

    def save_current(self) -> None:
        try:
            self.cli.save(self.file_var.get().strip())
        except Exception as exc:
            messagebox.showerror("Save failed", str(exc))

    def _rebuild_dynamic_panels(self) -> None:
        self.light_widgets = {}
        self.bitloader_input_vars = {}
        self.bitloader_speed_vars = {}
        self.bitloader_status_vars = {}
        self.momentary_state_vars = {}
        self.latch_vars = {}
        self.relay_coil_vars = {}

        for frame in (
            self.lights_frame,
            self.bitloaders_frame,
            self.switches_frame,
            self.relays_frame,
        ):
            for child in frame.winfo_children():
                child.destroy()

        if not self.cli.pc.state.lights:
            ttk.Label(self.lights_frame, text="No lights in module").pack(anchor="w")
        for light in self.cli.pc.state.lights:
            row = ttk.Frame(self.lights_frame)
            row.pack(fill="x", pady=2)
            canvas = tk.Canvas(row, width=22, height=22, highlightthickness=0)
            canvas.pack(side="left")
            oval = canvas.create_oval(3, 3, 19, 19, fill="#2e2e2e", outline="#666")
            label_var = tk.StringVar(value=f"{light.part_id} 0.00V")
            ttk.Label(row, textvariable=label_var).pack(side="left", padx=8)
            self.light_widgets[light.part_id] = (canvas, oval, label_var)

        if not self.cli.pc.state.bitloaders:
            ttk.Label(self.bitloaders_frame, text="No bitloaders in module").pack(
                anchor="w"
            )
        for loader in self.cli.pc.state.bitloaders:
            row = ttk.Frame(self.bitloaders_frame)
            row.pack(fill="x", pady=2)

            ttk.Label(row, text=loader.part_id, width=16).pack(side="left")

            input_var = tk.StringVar(value="")
            self.bitloader_input_vars[loader.part_id] = input_var
            ttk.Entry(row, textvariable=input_var, width=16).pack(side="left", padx=4)
            ttk.Button(
                row,
                text="Queue",
                command=lambda lid=loader.part_id: self.queue_gui_bits(lid),
            ).pack(side="left", padx=2)
            ttk.Button(
                row,
                text="Clear",
                command=lambda lid=loader.part_id: self.clear_gui_bits(lid),
            ).pack(side="left", padx=2)

            ttk.Label(row, text="speed").pack(side="left", padx=(8, 2))
            speed_var = tk.IntVar(value=max(1, int(loader.speed)))
            self.bitloader_speed_vars[loader.part_id] = speed_var
            speed_spin = ttk.Spinbox(
                row,
                from_=1,
                to=200,
                increment=1,
                textvariable=speed_var,
                width=5,
                command=lambda lid=loader.part_id: self.set_gui_loader_speed(lid),
            )
            speed_spin.pack(side="left", padx=2)
            speed_spin.bind(
                "<Return>",
                lambda _e, lid=loader.part_id: self.set_gui_loader_speed(lid),
            )
            speed_spin.bind(
                "<FocusOut>",
                lambda _e, lid=loader.part_id: self.set_gui_loader_speed(lid),
            )

            status_var = tk.StringVar(value="queue='' out=0.00V")
            self.bitloader_status_vars[loader.part_id] = status_var
            ttk.Label(row, textvariable=status_var).pack(side="left", padx=8)

        ttk.Label(self.switches_frame, text="Momentary").pack(anchor="w", pady=(0, 2))
        if not self.cli.pc.state.momentary_switches:
            ttk.Label(self.switches_frame, text="  (none)").pack(anchor="w")
        for switch in self.cli.pc.state.momentary_switches:
            row = ttk.Frame(self.switches_frame)
            row.pack(fill="x", pady=2)
            ttk.Label(row, text=switch.part_id, width=18).pack(side="left")
            button = ttk.Button(row, text="Hold")
            button.pack(side="left", padx=4)
            button.bind(
                "<ButtonPress-1>",
                lambda _e, sid=switch.part_id: self.set_momentary_state(sid, True),
            )
            button.bind(
                "<ButtonRelease-1>",
                lambda _e, sid=switch.part_id: self.set_momentary_state(sid, False),
            )
            button.bind(
                "<Leave>",
                lambda _e, sid=switch.part_id: self.set_momentary_state(sid, False),
            )
            ttk.Button(
                row,
                text="Tap",
                command=lambda sid=switch.part_id: self.tap_momentary(sid),
            ).pack(side="left", padx=4)
            state_var = tk.StringVar(value="released")
            ttk.Label(row, textvariable=state_var).pack(side="left", padx=8)
            self.momentary_state_vars[switch.part_id] = state_var

        ttk.Separator(self.switches_frame, orient="horizontal").pack(fill="x", pady=6)
        ttk.Label(self.switches_frame, text="Latching").pack(anchor="w", pady=(0, 2))
        if not self.cli.pc.state.latching_switches:
            ttk.Label(self.switches_frame, text="  (none)").pack(anchor="w")
        for switch in self.cli.pc.state.latching_switches:
            row = ttk.Frame(self.switches_frame)
            row.pack(fill="x", pady=2)
            var = tk.BooleanVar(value=switch.latched)
            chk = ttk.Checkbutton(
                row,
                text=switch.part_id,
                variable=var,
                command=lambda sid=switch.part_id, v=var: self.set_latch_state(sid, v),
            )
            chk.pack(side="left")
            self.latch_vars[switch.part_id] = var

        if not self.cli.pc.state.relays:
            ttk.Label(self.relays_frame, text="No relays in module").pack(anchor="w")
        for relay in self.cli.pc.state.relays:
            row = ttk.Frame(self.relays_frame)
            row.pack(fill="x", pady=2)
            ttk.Label(row, text=relay.part_id, width=18).pack(side="left")
            coil_var = tk.DoubleVar(value=relay.coil)
            self.relay_coil_vars[relay.part_id] = coil_var
            scale = ttk.Scale(
                row,
                from_=0.0,
                to=5.0,
                variable=coil_var,
                command=lambda value, rid=relay.part_id: self.set_relay_coil(rid, value),
            )
            scale.pack(side="left", fill="x", expand=True, padx=4)
            value_var = tk.StringVar(value=f"{relay.coil:.2f}V")
            ttk.Label(row, textvariable=value_var, width=9).pack(side="left")
            self.relay_coil_vars[f"{relay.part_id}:label"] = value_var

    def set_relay_coil(self, relay_id: str, value) -> None:
        if self.relay_update_guard:
            return
        relay = self.cli.pc.state.get_part(relay_id)
        if isinstance(relay, Relay):
            relay.coil = float(value)
            label_var = self.relay_coil_vars.get(f"{relay_id}:label")
            if isinstance(label_var, tk.StringVar):
                label_var.set(f"{relay.coil:.2f}V")

    def set_momentary_state(self, switch_id: str, pressed: bool) -> None:
        switch = self.cli.pc.state.get_part(switch_id)
        if isinstance(switch, MomentarySwitch):
            switch.pressed = bool(pressed)
            self.refresh_view()

    def tap_momentary(self, switch_id: str) -> None:
        switch = self.cli.pc.state.get_part(switch_id)
        if not isinstance(switch, MomentarySwitch):
            return
        switch.pressed = True
        self.cli.step(1, verbose=False)
        switch.pressed = False
        self.refresh_view()

    def set_latch_state(self, switch_id: str, var: tk.BooleanVar) -> None:
        switch = self.cli.pc.state.get_part(switch_id)
        if isinstance(switch, LatchingSwitch):
            switch.latched = bool(var.get())
            self.refresh_view()

    def queue_gui_bits(self, loader_id: str) -> None:
        part = self.cli.pc.state.get_part(loader_id)
        input_var = self.bitloader_input_vars.get(loader_id)
        if not isinstance(part, Bitloader) or input_var is None:
            return

        bits = input_var.get().strip()
        clean = part._sanitize_bits(bits)
        if clean:
            part.enqueue(clean)
        input_var.set("")
        self.refresh_view()

    def clear_gui_bits(self, loader_id: str) -> None:
        part = self.cli.pc.state.get_part(loader_id)
        if not isinstance(part, Bitloader):
            return
        part.input = ""
        part._buffer = ""
        part._step = 0
        part.out_v = 0.0
        self.refresh_view()

    def set_gui_loader_speed(self, loader_id: str) -> None:
        part = self.cli.pc.state.get_part(loader_id)
        speed_var = self.bitloader_speed_vars.get(loader_id)
        if not isinstance(part, Bitloader) or speed_var is None:
            return
        part.speed = max(1, int(speed_var.get()))
        speed_var.set(part.speed)
        self.refresh_view()

    def step_n(self, count: int) -> None:
        self.cli.step(count, verbose=False)
        self.refresh_view()

    def toggle_running(self) -> None:
        self.running = not self.running
        self.run_button_var.set("Pause" if self.running else "Run")
        if self.running:
            self._run_loop()

    def _run_loop(self) -> None:
        if not self.running:
            return
        self.cli.step(1, verbose=False)
        self.refresh_view()
        interval = max(20, int(self.interval_var.get()))
        self.root.after(interval, self._run_loop)

    def refresh_view(self) -> None:
        self.tick_var.set(f"Tick: {self.cli.tick}")

        for light in self.cli.pc.state.lights:
            data = self.light_widgets.get(light.part_id)
            if not data:
                continue
            canvas, oval, label_var = data
            color = "#1fd655" if light.on else "#2e2e2e"
            outline = "#88ff9b" if light.on else "#666666"
            canvas.itemconfigure(oval, fill=color, outline=outline)
            label_var.set(f"{light.part_id} {light.v:.2f}V")

        for loader in self.cli.pc.state.bitloaders:
            status_var = self.bitloader_status_vars.get(loader.part_id)
            if status_var is not None:
                status_var.set(
                    f"queue='{loader._buffer}' phase={loader._step} "
                    f"out={loader.out_v:.2f}V"
                )
            speed_var = self.bitloader_speed_vars.get(loader.part_id)
            if speed_var is not None:
                speed_var.set(max(1, int(loader.speed)))

        for switch in self.cli.pc.state.momentary_switches:
            state_var = self.momentary_state_vars.get(switch.part_id)
            if state_var is not None:
                state_var.set("pressed" if switch.pressed else "released")

        for switch in self.cli.pc.state.latching_switches:
            var = self.latch_vars.get(switch.part_id)
            if var is not None:
                var.set(bool(switch.latched))

        self.relay_update_guard = True
        try:
            for relay in self.cli.pc.state.relays:
                var = self.relay_coil_vars.get(relay.part_id)
                if isinstance(var, tk.DoubleVar):
                    var.set(relay.coil)
                label_var = self.relay_coil_vars.get(f"{relay.part_id}:label")
                if isinstance(label_var, tk.StringVar):
                    label_var.set(f"{relay.coil:.2f}V")
        finally:
            self.relay_update_guard = False

        self._update_status_text()

    def _update_status_text(self) -> None:
        lines = [f"Tick: {self.cli.tick}", ""]

        lines.append("Bitloaders:")
        if self.cli.pc.state.bitloaders:
            for loader in self.cli.pc.state.bitloaders:
                lines.append(
                    f"  {loader.part_id}: speed={loader.speed} phase={loader._step} "
                    f"queue='{loader._buffer}' out={loader.out_v:.2f}V"
                )
        else:
            lines.append("  (none)")

        lines.append("")
        lines.append("Momentary switches:")
        if self.cli.pc.state.momentary_switches:
            for switch in self.cli.pc.state.momentary_switches:
                lines.append(
                    f"  {switch.part_id}: pressed={switch.pressed} "
                    f"out={switch.out_v:.2f}V"
                )
        else:
            lines.append("  (none)")

        lines.append("")
        lines.append("Latching switches:")
        if self.cli.pc.state.latching_switches:
            for switch in self.cli.pc.state.latching_switches:
                lines.append(
                    f"  {switch.part_id}: latched={switch.latched} "
                    f"out={switch.out_v:.2f}V"
                )
        else:
            lines.append("  (none)")

        lines.append("")
        lines.append("Relays:")
        for relay in self.cli.pc.state.relays:
            lines.append(
                f"  {relay.part_id}: coil={relay.coil:.2f}V "
                f"NO={relay.norm_open:.2f}V NC={relay.norm_closed:.2f}V"
            )

        lines.append("")
        lines.append("Capacitors:")
        for cap in self.cli.pc.state.capacitors:
            lines.append(
                f"  {cap.part_id}: in={cap.in_v:.2f}V v={cap.v:.2f}V "
                f"charge={cap.charge_rate:.2f} discharge={cap.discharge_rate:.2f}"
            )

        lines.append("")
        lines.append("Diodes:")
        for diode in self.cli.pc.state.diodes:
            lines.append(
                f"  {diode.part_id}: in={diode.v:.2f}V out={diode.out_v:.2f}V"
            )

        text = "\n".join(lines)
        self.status_text.configure(state="normal")
        self.status_text.delete("1.0", "end")
        self.status_text.insert("1.0", text)
        self.status_text.configure(state="disabled")

    def start(self) -> None:
        self.root.mainloop()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Relay computer simulator")
    parser.add_argument(
        "file",
        nargs="?",
        default="module.pc1",
        help="Path to a .pc1 module (default: module.pc1)",
    )
    parser.add_argument(
        "--steps",
        type=int,
        default=0,
        help="Run this many steps immediately after loading",
    )
    parser.add_argument(
        "--status",
        action="store_true",
        help="Print full status after loading/stepping",
    )
    parser.add_argument(
        "--no-repl",
        action="store_true",
        help="Run initial actions and exit without interactive prompt",
    )
    parser.add_argument(
        "--gui",
        action="store_true",
        help="Launch Tkinter GUI with visual indicators",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        if args.gui:
            cli = SimulatorCLI()
            gui = SimulatorGUI(cli, args.file)
            if args.steps:
                gui.step_n(args.steps)
            gui.start()
            return 0

        cli = SimulatorCLI()
        cli.load(args.file)

        if args.steps:
            cli.step(args.steps, verbose=False)

        if args.status or args.steps:
            cli.status()

        if not args.no_repl:
            cli.repl()

        return 0
    except Exception as exc:
        print(f"Fatal: {exc}")
        return 1


if __name__ == "__main__":
    sys.exit(main())

