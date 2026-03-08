from __future__ import annotations

import argparse
import contextlib
import io
import shlex
import sys
import time
from pathlib import Path
import tkinter as tk
from tkinter import filedialog

from simulator import Bitloader, LatchingSwitch, MomentarySwitch, Relay, Sim, Wire


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
        self.sim = Sim(version="1.0")
        self.loaded_file: Path | None = None

    def _get_components_by_type(self, comp_type):
        """Get all components of a specific type"""
        return [
            comp
            for comp in self.sim.components.values()
            if type(comp).__name__.lower() == comp_type.replace("_", "").lower()
        ]

    def load(self, filename: str) -> None:
        path = Path(filename)
        if not path.exists():
            raise FileNotFoundError(f"File not found: {filename}")

        self.sim.load_sim_state(str(path))
        self.loaded_file = path
        print(f"Loaded {path} (name: {self.sim.name})")

        # Count components by type
        bitloaders = self._get_components_by_type("bitloader")
        relays = self._get_components_by_type("relay")
        diodes = self._get_components_by_type("diode")
        capacitors = self._get_components_by_type("capacitor")
        lights = self._get_components_by_type("light")
        momentary_switches = self._get_components_by_type("momentary_switch")
        latching_switches = self._get_components_by_type("latching_switch")
        wires = [
            comp for comp in self.sim.components.values() if isinstance(comp, Wire)
        ]

        print(
            "Parts: "
            f"{len(bitloaders)} bitloaders, "
            f"{len(relays)} relays, "
            f"{len(diodes)} diodes, "
            f"{len(capacitors)} capacitors, "
            f"{len(lights)} lights, "
            f"{len(momentary_switches)} momentary switches, "
            f"{len(latching_switches)} latching switches, "
            f"{len(wires)} wires"
        )

    def save(self, filename: str | None = None) -> None:
        if filename:
            out = Path(filename)
        elif self.loaded_file:
            out = self.loaded_file
        else:
            raise ValueError("No target file specified.")

        self.sim.save_sim_state(str(out))
        print(f"Saved {out}.")

    def step(self, count: int = 1, verbose: bool = True) -> None:
        if count < 1:
            raise ValueError("Step count must be >= 1")

        for _ in range(count):
            self.sim.step()

        if verbose:
            print(f"Advanced {count} step(s). Tick={self.sim.curr_step}")
            self.show_lights()

    def run(self, count: int, delay_s: float = 0.0) -> None:
        if count < 1:
            raise ValueError("Run count must be >= 1")
        if delay_s < 0:
            raise ValueError("Delay must be >= 0")

        for _ in range(count):
            self.step(1, verbose=False)
            print(f"Tick={self.sim.curr_step}", end=" ")
            self.show_lights(prefix="")
            if delay_s:
                time.sleep(delay_s)

    def show_lights(self, prefix: str = "Lights: ") -> None:
        lights = self._get_components_by_type("light")
        if not lights:
            print("No lights present.")
            return

        states = []
        for light in lights:
            states.append(
                f"{light.part_id}={'ON' if light.on else 'off'}({light.vcc:.2f}V)"
            )
        print(prefix + " ".join(states))

    def status(self) -> None:
        print(f"Tick: {self.sim.curr_step}")

        bitloaders = self._get_components_by_type("bitloader")
        if bitloaders:
            print("Bitloaders:")
            for loader in bitloaders:
                print(
                    f"  {loader.part_id}: speed={loader.speed} phase={loader._step} "
                    f"queue='{loader._buffer}' out={loader.out_v:.2f}V"
                )

        momentary_switches = self._get_components_by_type("momentary_switch")
        if momentary_switches:
            print("Momentary switches:")
            for switch in momentary_switches:
                print(
                    f"  {switch.part_id}: pressed={switch.pressed} "
                    f"out={switch.out_v:.2f}V vcc={switch.vcc:.2f}V"
                )

        latching_switches = self._get_components_by_type("latching_switch")
        if latching_switches:
            print("Latching switches:")
            for switch in latching_switches:
                print(
                    f"  {switch.part_id}: latched={switch.latched} "
                    f"out={switch.out_v:.2f}V vcc={switch.vcc:.2f}V"
                )

        relays = self._get_components_by_type("relay")
        if relays:
            print("Relays:")
            for relay in relays:
                print(
                    f"  {relay.part_id}: coil={relay.coil:.2f}V vcc={relay.vcc:.2f}V "
                    f"NO={relay.norm_open:.2f}V NC={relay.norm_closed:.2f}V"
                )

        diodes = self._get_components_by_type("diode")
        if diodes:
            print("Diodes:")
            for diode in diodes:
                print(
                    f"  {diode.part_id}: in={diode.vcc:.2f}V out={diode.out_v:.2f}V "
                    f"th={diode.forward_threshold:.2f}V"
                )

        capacitors = self._get_components_by_type("capacitor")
        if capacitors:
            print("Capacitors:")
            for cap in capacitors:
                print(
                    f"  {cap.part_id}: in={cap.vcc:.2f}V v={cap.v:.2f}V "
                    f"max={cap.max_v:.2f}V"
                )

        self.show_lights()

    def list_parts(self, kind: str = "all") -> None:
        kinds = {
            "bitloader": self._get_components_by_type("bitloader"),
            "relay": self._get_components_by_type("relay"),
            "wire": [c for c in self.sim.components.values() if isinstance(c, Wire)],
            "light": self._get_components_by_type("light"),
            "capacitor": self._get_components_by_type("capacitor"),
            "diode": self._get_components_by_type("diode"),
            "momentary_switch": self._get_components_by_type("momentary_switch"),
            "latching_switch": self._get_components_by_type("latching_switch"),
            "ground": self._get_components_by_type("ground"),
            "drain": self._get_components_by_type("drain"),
        }

        if kind == "all":
            for key, items in kinds.items():
                if items:
                    print(f"{key}s: {[p.part_id for p in items]}")
            return

        if kind not in kinds:
            raise ValueError(
                "kind must be one of: all bitloader relay wire light "
                "capacitor diode momentary_switch latching_switch ground drain"
            )

        print([p.part_id for p in kinds[kind]])

    def show_part(self, part_id: str) -> None:
        part = self.sim.components.get(part_id)
        if part is None:
            raise ValueError(f"Unknown part id: {part_id}")

        attrs = {
            key: value for key, value in vars(part).items() if not key.startswith("_")
        }
        print(f"{part_id}: {attrs}")

    def set_attr(self, part_id: str, attr: str, raw_value: str) -> None:
        part = self.sim.components.get(part_id)
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
        part = self.sim.components.get(relay_id)
        if not isinstance(part, Relay):
            raise ValueError(f"{relay_id} is not a relay")

        part.coil = float(value)
        print(f"Set {relay_id}.coil = {part.coil}")

    def pulse(self, relay_id: str, value: float, steps: int) -> None:
        part = self.sim.components.get(relay_id)
        if not isinstance(part, Relay):
            raise ValueError(f"{relay_id} is not a relay")
        if steps < 1:
            raise ValueError("steps must be >= 1")

        prev = part.coil
        part.coil = float(value)
        self.step(steps, verbose=False)
        part.coil = prev
        print(f"Pulsed {relay_id}.coil={value} for {steps} step(s), restored {prev}")
        self.show_lights()

    def set_momentary(self, switch_id: str, pressed: bool) -> None:
        part = self.sim.components.get(switch_id)
        if not isinstance(part, MomentarySwitch):
            raise ValueError(f"{switch_id} is not a momentary switch")
        part.pressed = bool(pressed)
        print(f"Set {switch_id}.pressed = {part.pressed}")

    def set_latch(self, switch_id: str, latched: bool) -> None:
        part = self.sim.components.get(switch_id)
        if not isinstance(part, LatchingSwitch):
            raise ValueError(f"{switch_id} is not a latching switch")
        part.latched = bool(latched)
        print(f"Set {switch_id}.latched = {part.latched}")

    def toggle_latch(self, switch_id: str) -> None:
        part = self.sim.components.get(switch_id)
        if not isinstance(part, LatchingSwitch):
            raise ValueError(f"{switch_id} is not a latching switch")
        part.toggle()
        print(f"Toggled {switch_id}.latched -> {part.latched}")

    def queue_bits(self, loader_id: str, bits: str) -> None:
        part = self.sim.components.get(loader_id)
        if not isinstance(part, Bitloader):
            raise ValueError(f"{loader_id} is not a bitloader")
        clean = part._sanitize_bits(bits)
        if not clean:
            raise ValueError("Bits must contain at least one 0 or 1")
        part.enqueue(clean)
        print(f"Queued {len(clean)} bits into {loader_id}: {clean}")

    def set_bitloader_speed(self, loader_id: str, speed: int) -> None:
        part = self.sim.components.get(loader_id)
        if not isinstance(part, Bitloader):
            raise ValueError(f"{loader_id} is not a bitloader")
        part.speed = max(1, int(speed))
        print(f"Set {loader_id}.speed = {part.speed}")

    def clear_bitloader(self, loader_id: str) -> None:
        part = self.sim.components.get(loader_id)
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
        print("  load <file.sim>")
        print("  save [file.sim]")
        print("  status")
        print("  lights")
        print(
            "  list [all|bitloader|relay|wire|light|capacitor|diode|"
            "momentary_switch|latching_switch|ground|drain]"
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

    def exec(self, line: str) -> bool:
        if not line.strip():
            return True

        try:
            tokens = shlex.split(line)
        except ValueError as e:
            print(f"Parse error: {e}")
            return True

        cmd = tokens[0].lower()

        try:
            if cmd == "help":
                self.help()
            elif cmd == "quit" or cmd == "exit":
                return False
            elif cmd == "load":
                if len(tokens) < 2:
                    print("Usage: load <file.sim>")
                else:
                    self.load(tokens[1])
            elif cmd == "save":
                if len(tokens) > 1:
                    self.save(tokens[1])
                else:
                    self.save()
            elif cmd == "status":
                self.status()
            elif cmd == "lights":
                self.show_lights()
            elif cmd == "list":
                kind = tokens[1] if len(tokens) > 1 else "all"
                self.list_parts(kind)
            elif cmd == "show":
                if len(tokens) < 2:
                    print("Usage: show <part_id>")
                else:
                    self.show_part(tokens[1])
            elif cmd == "step":
                count = int(tokens[1]) if len(tokens) > 1 else 1
                self.step(count)
            elif cmd == "run":
                if len(tokens) < 2:
                    print("Usage: run <count> [delay_seconds]")
                else:
                    count = int(tokens[1])
                    delay = float(tokens[2]) if len(tokens) > 2 else 0.0
                    self.run(count, delay)
            elif cmd == "queue":
                if len(tokens) < 3:
                    print("Usage: queue <bitloader_id> <bit-string>")
                else:
                    self.queue_bits(tokens[1], tokens[2])
            elif cmd == "bspeed":
                if len(tokens) < 3:
                    print("Usage: bspeed <bitloader_id> <speed>")
                else:
                    self.set_bitloader_speed(tokens[1], int(tokens[2]))
            elif cmd == "bclear":
                if len(tokens) < 2:
                    print("Usage: bclear <bitloader_id>")
                else:
                    self.clear_bitloader(tokens[1])
            elif cmd == "coil":
                if len(tokens) < 3:
                    print("Usage: coil <relay_id> <voltage>")
                else:
                    self.set_coil(tokens[1], float(tokens[2]))
            elif cmd == "pulse":
                if len(tokens) < 4:
                    print("Usage: pulse <relay_id> <voltage> <steps>")
                else:
                    self.pulse(tokens[1], float(tokens[2]), int(tokens[3]))
            elif cmd == "press":
                if len(tokens) < 2:
                    print("Usage: press <momentary_switch_id>")
                else:
                    self.set_momentary(tokens[1], True)
            elif cmd == "release":
                if len(tokens) < 2:
                    print("Usage: release <momentary_switch_id>")
                else:
                    self.set_momentary(tokens[1], False)
            elif cmd == "latch":
                if len(tokens) < 3:
                    print("Usage: latch <latching_switch_id> <on|off>")
                else:
                    value = _to_value(tokens[2])
                    self.set_latch(tokens[1], bool(value))
            elif cmd == "toggle":
                if len(tokens) < 2:
                    print("Usage: toggle <latching_switch_id>")
                else:
                    self.toggle_latch(tokens[1])
            elif cmd == "set":
                if len(tokens) < 4:
                    print("Usage: set <part_id> <attr> <value>")
                else:
                    self.set_attr(tokens[1], tokens[2], tokens[3])
            else:
                print(f"Unknown command: {cmd}. Type 'help' for available commands.")
        except Exception as e:
            print(f"Error: {e}")

        return True


class SimulatorGUI:
    def __init__(self, cli: SimulatorCLI, initial_file: str | None = None) -> None:
        self.cli = cli
        self.root = tk.Tk()
        self.root.title("PC Simulator")
        self.root.geometry("900x620")

        self.current_file_var = tk.StringVar(
            value=str(cli.loaded_file) if cli.loaded_file else "(no file loaded)"
        )
        self.step_count_var = tk.StringVar(value="1")
        self.run_count_var = tk.StringVar(value="10")
        self.run_delay_var = tk.StringVar(value="0")
        self.command_var = tk.StringVar()

        self._build_layout()

        if initial_file:
            self._run_command(f'load "{initial_file}"')

    def _build_layout(self) -> None:
        top = tk.Frame(self.root, padx=10, pady=10)
        top.pack(fill=tk.X)

        tk.Label(top, text="File:").pack(side=tk.LEFT)
        tk.Label(top, textvariable=self.current_file_var, anchor="w").pack(
            side=tk.LEFT, fill=tk.X, expand=True, padx=(6, 10)
        )

        tk.Button(top, text="Load", command=self._on_load).pack(side=tk.LEFT, padx=2)
        tk.Button(top, text="Save", command=self._on_save).pack(side=tk.LEFT, padx=2)
        tk.Button(top, text="Status", command=lambda: self._run_command("status")).pack(
            side=tk.LEFT, padx=2
        )
        tk.Button(top, text="Lights", command=lambda: self._run_command("lights")).pack(
            side=tk.LEFT, padx=2
        )

        controls = tk.Frame(self.root, padx=10, pady=5)
        controls.pack(fill=tk.X)

        tk.Label(controls, text="Step Count:").pack(side=tk.LEFT)
        tk.Entry(controls, textvariable=self.step_count_var, width=6).pack(
            side=tk.LEFT, padx=(4, 10)
        )
        tk.Button(controls, text="Step", command=self._on_step).pack(
            side=tk.LEFT, padx=2
        )

        tk.Label(controls, text="Run Count:").pack(side=tk.LEFT, padx=(12, 0))
        tk.Entry(controls, textvariable=self.run_count_var, width=6).pack(
            side=tk.LEFT, padx=(4, 8)
        )
        tk.Label(controls, text="Delay(s):").pack(side=tk.LEFT)
        tk.Entry(controls, textvariable=self.run_delay_var, width=6).pack(
            side=tk.LEFT, padx=(4, 10)
        )
        tk.Button(controls, text="Run", command=self._on_run).pack(side=tk.LEFT, padx=2)

        command_row = tk.Frame(self.root, padx=10, pady=5)
        command_row.pack(fill=tk.X)
        tk.Label(command_row, text="Command:").pack(side=tk.LEFT)
        cmd_entry = tk.Entry(command_row, textvariable=self.command_var)
        cmd_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(6, 8))
        cmd_entry.bind("<Return>", lambda _event: self._on_command())
        tk.Button(command_row, text="Run Command", command=self._on_command).pack(
            side=tk.LEFT
        )

        log_frame = tk.Frame(self.root, padx=10, pady=10)
        log_frame.pack(fill=tk.BOTH, expand=True)

        self.log_text = tk.Text(log_frame, wrap="word", state=tk.DISABLED)
        self.log_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scroll = tk.Scrollbar(log_frame, command=self.log_text.yview)
        scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self.log_text.configure(yscrollcommand=scroll.set)

        self._append_log("GUI ready. Use Load to open a .sim file.")

    def _append_log(self, text: str) -> None:
        self.log_text.configure(state=tk.NORMAL)
        self.log_text.insert(tk.END, text.rstrip() + "\n")
        self.log_text.see(tk.END)
        self.log_text.configure(state=tk.DISABLED)

    def _run_command(self, command: str) -> None:
        self._append_log(f"> {command}")

        capture = io.StringIO()
        with contextlib.redirect_stdout(capture):
            keep_running = self.cli.exec(command)

        output = capture.getvalue().rstrip()
        if output:
            self._append_log(output)

        self.current_file_var.set(
            str(self.cli.loaded_file) if self.cli.loaded_file else "(no file loaded)"
        )

        if not keep_running:
            self.root.destroy()

    def _on_load(self) -> None:
        path = filedialog.askopenfilename(
            title="Open simulation",
            filetypes=[("Simulation files", "*.sim"), ("All files", "*.*")],
        )
        if path:
            self._run_command(f'load "{path}"')

    def _on_save(self) -> None:
        default_name = "demo.sim"
        if self.cli.loaded_file is not None:
            default_name = self.cli.loaded_file.name

        path = filedialog.asksaveasfilename(
            title="Save simulation",
            defaultextension=".sim",
            initialfile=default_name,
            filetypes=[("Simulation files", "*.sim"), ("All files", "*.*")],
        )
        if path:
            self._run_command(f'save "{path}"')

    def _on_step(self) -> None:
        value = self.step_count_var.get().strip() or "1"
        self._run_command(f"step {value}")

    def _on_run(self) -> None:
        count = self.run_count_var.get().strip() or "1"
        delay = self.run_delay_var.get().strip() or "0"
        self._run_command(f"run {count} {delay}")

    def _on_command(self) -> None:
        command = self.command_var.get().strip()
        if not command:
            return
        self.command_var.set("")
        self._run_command(command)

    def run(self) -> None:
        self.root.mainloop()


def main():
    parser = argparse.ArgumentParser(description="Simulator CLI")
    parser.add_argument("file", nargs="?", help="Sim file to load (.sim)")
    parser.add_argument("-c", "--command", help="Execute a single command and exit")
    parser.add_argument("--gui", action="store_true", help="Launch Tkinter GUI")

    args = parser.parse_args()

    cli = SimulatorCLI()

    if args.gui:
        gui = SimulatorGUI(cli, initial_file=args.file)
        gui.run()
        return

    if args.file:
        try:
            cli.load(args.file)
        except Exception as e:
            print(f"Failed to load {args.file}: {e}")
            sys.exit(1)

    if args.command:
        cli.exec(args.command)
        return

    print("Simulator CLI. Type 'help' for commands.")

    while True:
        try:
            line = input("> ")
            if not cli.exec(line):
                break
        except EOFError:
            break
        except KeyboardInterrupt:
            print("\nInterrupted. Type 'quit' to exit.")
            continue


if __name__ == "__main__":
    main()
