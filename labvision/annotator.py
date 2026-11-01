"""Local Tkinter annotation UI. Pillow is required for JPEG/PNG display."""

import json
from pathlib import Path

from .annotation import (add_component, add_port, add_wire, annotate, candidate_from_session,
                         invalidate, new_session, remove_item, set_calibration, verify_session)
from .annotation import training_record, add_outer_hole, set_external_terminal, set_rail_groups
from .assistance import accept_object_draft
from .detector_review import import_predictions, assign_proposal
from .core import CandidateError, compile_netlist, confirm, endpoints, require, endpoint_label
from .geometry import board_fingerprint, calibration_quality, hole_positions, project


def launch(image_path, board, assembly_id, candidate=None, session_path=None):
    import tkinter as tk
    from tkinter import filedialog, messagebox, simpledialog, ttk
    try:
        from PIL import Image, ImageTk
    except ImportError as exc:
        raise CandidateError("Install Pillow: python -m pip install -r requirements-vision.txt") from exc

    source = Path(image_path)
    # Keep native file pixel coordinates; EXIF rotation is deliberately not applied.
    with Image.open(source) as opened:
        photo = opened.convert("RGB")
    session = (verify_session(json.loads(Path(session_path).read_text(encoding="utf-8-sig")), source)
               if session_path else new_session(source, photo.size, board, assembly_id, candidate))
    require(session["image_size"] == list(photo.size), "session image dimensions differ")
    require(board_fingerprint(session["board"]) == board_fingerprint(board), "session board profile differs")

    class Annotator:
        def __init__(self):
            self.session = session
            self.anchors = []
            self.mode = "annotate"
            self.scale = min(1.0, 980 / photo.width, 760 / photo.height)
            self.targets = []
            self.last_revision = None
            self.root = tk.Tk()
            self.root.title("Git-Good · Board calibration and endpoint annotation")
            if session.get("assistance"):
                self.root.title("Git-Good · Assisted draft — review suggested connections")
            self.root.geometry(f"{min(1280, self.root.winfo_screenwidth()-50)}x"
                               f"{min(880, self.root.winfo_screenheight()-80)}")
            self.status = tk.StringVar()
            self.board_ack = tk.BooleanVar()
            self.review_ack = tk.BooleanVar()
            self.show_grid = tk.BooleanVar(value=not bool(session.get("assistance")))
            self.show_all = tk.BooleanVar(value=not bool(session.get("assistance")))
            pane = ttk.Frame(self.root, padding=10)
            pane.pack(side="left", fill="y")
            ttk.Label(pane, text="1  Calibrate", font=("Segoe UI", 12, "bold")).pack(anchor="w")
            ttk.Button(pane, text="Pick 4 known hole centers", command=self.start_calibration).pack(fill="x")
            ttk.Button(pane, text="Check another known hole", command=lambda: self.set_mode("check")).pack(fill="x")
            ttk.Button(pane, text="Add outer rail hole", command=lambda: self.set_mode("outer")).pack(fill="x")
            ttk.Button(pane, text="Review rail connections", command=self.guard(self.rails)).pack(fill="x")
            ttk.Label(pane, text="2  Add and label objects", font=("Segoe UI", 12, "bold")).pack(anchor="w", pady=(12, 0))
            for text, action in (("Add component", self.component), ("Add wire (a + b)", self.wire),
                                 ("Add input/output/supply port", self.port),
                                 ("Edit selected component value", self.value),
                                 ("Remove selected object", self.remove)):
                ttk.Button(pane, text=text, command=self.guard(action)).pack(fill="x")
            self.listbox = tk.Listbox(pane, width=36, height=8, exportselection=False)
            self.listbox.pack(fill="both", expand=True, pady=6)
            self.listbox.bind("<<ListboxSelect>>", lambda _: self.show_selected())
            ttk.Button(pane, text="Accept object's draft", command=self.guard(self.accept_draft)).pack(fill="x")
            ttk.Button(pane, text="Load detector predictions", command=self.guard(self.load_detector)).pack(fill="x")
            ttk.Button(pane, text="Use proposal for selected endpoint", command=self.guard(self.use_detector)).pack(fill="x")
            ttk.Button(pane, text="Click selected endpoint", command=lambda: self.set_mode("annotate")).pack(fill="x")
            ttk.Button(pane, text="Label as external terminal", command=self.guard(self.external)).pack(fill="x")
            ttk.Button(pane, text="Mark selected endpoint hidden", command=self.guard(self.hidden)).pack(fill="x")
            ttk.Label(pane, text="3  Save and export", font=("Segoe UI", 12, "bold")).pack(anchor="w", pady=(12, 0))
            ttk.Checkbutton(pane, text="Board topology and part orientation checked", variable=self.board_ack).pack(anchor="w")
            ttk.Checkbutton(pane, text="All connections, pairing and omissions reviewed", variable=self.review_ack).pack(anchor="w")
            ttk.Button(pane, text="Save annotation session", command=self.guard(self.save)).pack(fill="x")
            ttk.Button(pane, text="Export reviewed training labels", command=self.guard(self.export_labels)).pack(fill="x")
            ttk.Button(pane, text="Export unreviewed candidate", command=self.guard(self.export_candidate)).pack(fill="x")
            ttk.Button(pane, text="Export reviewed netlist", command=self.guard(self.export_netlist)).pack(fill="x")
            ttk.Label(pane, textvariable=self.status, wraplength=300).pack(anchor="w", pady=8)
            body = ttk.Frame(self.root)
            body.pack(side="right", fill="both", expand=True)
            ttk.Label(body, text="Click insertion points at board level. Mouse wheel zooms; scrollbars pan. "
                      "Save partial sessions at any time.").pack(fill="x")
            self.canvas = tk.Canvas(body, background="#202631", highlightthickness=0)
            horizontal = ttk.Scrollbar(body, orient="horizontal", command=self.canvas.xview)
            vertical = ttk.Scrollbar(body, orient="vertical", command=self.canvas.yview)
            horizontal.pack(side="bottom", fill="x")
            vertical.pack(side="right", fill="y")
            self.canvas.pack(fill="both", expand=True)
            self.canvas.configure(xscrollcommand=horizontal.set, yscrollcommand=vertical.set)
            self.canvas.bind("<Button-1>", self.guard(self.click))
            self.canvas.bind("<MouseWheel>", self.zoom)
            ttk.Checkbutton(body, text="Show hole grid", variable=self.show_grid, command=self.draw).pack()
            ttk.Checkbutton(body, text="Show all endpoint labels", variable=self.show_all, command=self.draw).pack()
            self.refresh()

        def guard(self, action):
            def wrapped(*args):
                try:
                    action(*args)
                except (CandidateError, ValueError, KeyError, OSError) as exc:
                    messagebox.showerror("Review needed", str(exc), parent=self.root)
            return wrapped

        def set_mode(self, mode):
            self.mode = mode
            self.status.set({"check": "Click a separate known hole, then enter its ID.",
                             "outer": "Click the center of an outer rail hole. Its connectivity remains unverified.",
                             "annotate": "Select an endpoint, then click where it enters the board."}[mode])

        def start_calibration(self):
            self.anchors = []
            self.mode = "calibrate"
            self.status.set("Click 4 widely separated known hole centers. Enter actual printed hole IDs.")

        def selected(self):
            index = self.listbox.curselection()
            require(bool(index), "select an endpoint from the list")
            return self.targets[index[0]]

        def refresh(self, selected=None):
            revision = self.session["candidate"]["revision"]
            if self.last_revision != revision:
                self.board_ack.set(False)
                self.review_ack.set(False)
            self.last_revision = revision
            old = selected or (self.targets[self.listbox.curselection()[0]]
                               if self.listbox.curselection() else None)
            self.targets = []
            self.listbox.delete(0, "end")
            for name, p, _ in endpoints(self.session["candidate"]):
                self.targets.append(name)
                marker = "~" if p.get("source") == "vision" else " "
                self.listbox.insert("end", f"{marker} {name:12}  {endpoint_label(p)}")
            if self.targets:
                self.listbox.selection_set(self.targets.index(old) if old in self.targets else 0)
            self.draw()
            calibration = self.session.get("calibration")
            if calibration:
                quality = calibration_quality(calibration, self.session["board"])
                self.status.set(f"Calibration {'validated' if quality['validated'] else 'needs checks'}; "
                                f"{quality['check_count']} check holes. Revision {self.session['candidate']['revision']}.")
            else:
                self.status.set("Start with 4 known hole centers; add 2 check holes after calibration.")

        def draw(self):
            self.canvas.delete("all")
            size = (max(1, round(photo.width*self.scale)), max(1, round(photo.height*self.scale)))
            self.tk_photo = ImageTk.PhotoImage(photo.resize(size, Image.Resampling.LANCZOS))
            self.canvas.create_image(0, 0, image=self.tk_photo, anchor="nw")
            self.canvas.configure(scrollregion=(0, 0, *size))
            calibration = self.session.get("calibration")
            if calibration and self.show_grid.get():
                for hole, xy in hole_positions(self.session["board"]).items():
                    try:
                        x, y = project(calibration["board_to_image"], xy)
                        if 0 <= x < photo.width and 0 <= y < photo.height:
                            x, y = x*self.scale, y*self.scale
                            self.canvas.create_oval(x-2, y-2, x+2, y+2, outline="#00e5c0")
                    except CandidateError:
                        continue
            selected = self.targets[self.listbox.curselection()[0]] if self.listbox.curselection() else None
            for name, p, _ in endpoints(self.session["candidate"]):
                if not self.show_all.get() and selected and name.split(".")[0] != selected.split(".")[0]:
                    continue
                if p.get("image_xy") is None:
                    continue
                x, y = [v*self.scale for v in p["image_xy"]]
                color = "#ffdf61" if name == selected else ("#ffab40" if p.get("source") == "vision" else "#ff6a97")
                self.canvas.create_oval(x-4, y-4, x+4, y+4, outline=color, width=2)
                self.canvas.create_text(x+6, y-6, text=name, fill=color, anchor="sw")

            for proposal in self.session.get('detector_proposals', {}).get('proposals', []):
                box = [v*self.scale for v in proposal['box']]
                self.canvas.create_rectangle(*box, outline='#00ffff', width=2)
                self.canvas.create_text(box[0], box[1], text=proposal['id'], fill='#00ffff', anchor='sw')

        def load_detector(self):
            filename = filedialog.askopenfilename(filetypes=[('Prediction JSON', '*.json')])
            if not filename:
                return
            count = import_predictions(self.session, json.loads(Path(filename).read_text(encoding='utf-8')))
            self.draw()
            self.status.set(f'{count} proposals loaded. Add a wire, select its endpoint, then choose a proposal. Pairing is your review decision.')

        def use_detector(self):
            target = self.selected()
            identifier = simpledialog.askstring('Detector proposal', f'Proposal ID for {target} (for example P1):', parent=self.root)
            if not identifier:
                return
            result = assign_proposal(self.session, target, identifier.strip())
            self.refresh(target)
            self.status.set(f"{target}: {result['hole'] or 'unresolved'}. Inspect insertion point; click to correct. No pairing confirmed.")

        def show_selected(self):
            self.draw()
            if not self.listbox.curselection():
                return
            target = self.selected()
            p = next(p for name, p, _ in endpoints(self.session["candidate"]) if name == target)
            self.status.set(f"{target}: {endpoint_label(p)}. {p.get('reason', '')}")

        def external(self):
            target = self.selected()
            identifier = simpledialog.askstring("External terminal",
                "Terminal ID, e.g. CLIP_BOTTOM. Reuse a name only for the same physical connection.\n"
                "An existing click outside the grid is preserved. Supply polarity stays unknown.", parent=self.root)
            if identifier:
                set_external_terminal(self.session, target, identifier.strip())
                self.refresh(target)
                self.status.set(f"{target}: external:{identifier.strip()}. Supply role still needs verification.")

        def rails(self):
            board = self.session["board"]
            holes = set(board.get("rail_holes", board.get("unverified_rail_holes", [])))
            require(holes, "add outer rail holes first")
            groups = [g for g in board["groups"] if set(g) <= holes]
            text = simpledialog.askstring("Rail connections",
                "One connected segment per group. Separate holes by commas and groups by semicolons.\n"
                "Keep different tracks and the two halves separate; include every recorded rail hole.",
                initialvalue="; ".join(",".join(g) for g in groups), parent=self.root)
            if not text:
                return
            groups = [[h.strip().upper() for h in group.split(",")]
                      for group in text.split(";")]
            if messagebox.askyesno("Verify rail connectivity",
                    "Have you checked that each group is electrically connected on the actual board, "
                    "and that rail breaks and different tracks remain separate?", parent=self.root):
                set_rail_groups(self.session, groups, reviewed=True,
                                evidence="User explicitly verified rail groups in annotation UI")
                self.refresh()
                self.status.set("Rail groups reviewed. Whole-circuit review still required before netlist export.")

        def accept_draft(self):
            identifier = self.selected().split(".")[0]
            count = accept_object_draft(self.session, identifier)
            self.refresh()
            self.status.set(f"Accepted {count} mapped endpoints for {identifier}. Any '?' entries still need resolution.")

        def zoom(self, event):
            self.scale = max(0.1, min(6, self.scale * (1.2 if event.delta > 0 else 1/1.2)))
            self.draw()

        def click(self, event):
            xy = [self.canvas.canvasx(event.x)/self.scale, self.canvas.canvasy(event.y)/self.scale]
            if not (0 <= xy[0] < photo.width and 0 <= xy[1] < photo.height):
                return
            if self.mode == "outer":
                positions = hole_positions(self.session["board"])
                number = 1
                while f"R{number}" in positions:
                    number += 1
                identifier = f"R{number}"
                add_outer_hole(self.session, identifier, xy)
                self.mode = "annotate"
                self.refresh()
                self.status.set(f"Added {identifier}. Select an endpoint and click this hole. Rail connectivity unverified.")
                return
            if self.mode in ("calibrate", "check"):
                hole = simpledialog.askstring("Known hole", "Actual hole ID (for example A1 or J30):", parent=self.root)
                if not hole:
                    return
                record = {"hole": hole.strip().upper(), "xy": xy}
                if self.mode == "calibrate":
                    proposed = self.anchors + [record]
                    require(record["hole"] in hole_positions(self.session["board"]), "unknown hole")
                    require(record["hole"] not in {a["hole"] for a in self.anchors}, "use distinct anchor holes")
                    if len(proposed) == 4:
                        set_calibration(self.session, proposed)
                        self.mode = "check"
                        self.anchors = []
                        self.refresh()
                    else:
                        self.anchors = proposed
                        self.status.set(f"Anchor {len(proposed)}/4 saved; choose the next known hole center.")
                else:
                    require(self.session.get("calibration") is not None, "calibrate first")
                    calibration = self.session["calibration"]
                    proposed = dict(calibration, checks=calibration["checks"] + [record])
                    quality = calibration_quality(proposed, self.session["board"])
                    require(quality["max_error_pitch"] <= 0.25,
                            "Check exceeds 0.25 hole pitch; check hole ID or recalibrate")
                    self.session["calibration"] = proposed
                    self.refresh()
            else:
                target = self.selected()
                result = annotate(self.session, target, xy)
                self.board_ack.set(False)
                self.review_ack.set(False)
                self.refresh(target)
                self.status.set(f"{target}: {result['hole'] or 'ambiguous — zoom and click again'}. "
                                "Pair both ends of each wire under the same wire ID.")

        def next_id(self, prefix):
            used = {obj["id"] for field in ("components", "wires", "ports")
                    for obj in self.session["candidate"][field]}
            i = 1
            while f"{prefix}{i}" in used:
                i += 1
            return f"{prefix}{i}"

        def component(self):
            part = simpledialog.askstring("Component", "Part: 7400, resistor, capacitor, led, diode, opamp\nOpamp uses functional terminals; verify actual package pinout.", initialvalue="7400", parent=self.root)
            if not part:
                return
            prefix = {"7400": "U", "resistor": "R", "capacitor": "C", "led": "D", "diode": "D", "opamp": "U"}.get(part, "U")
            value = None
            if part in ("resistor", "capacitor"):
                value = simpledialog.askfloat("Component value", "SI value (ohms or farads); Cancel if unknown", parent=self.root)
            identifier = self.next_id(prefix)
            add_component(self.session, part, identifier, value)
            self.refresh()

        def wire(self):
            identifier = self.next_id("W")
            add_wire(self.session, identifier)
            self.refresh(identifier + ".a")
            self.set_mode("annotate")

        def port(self):
            role = simpledialog.askstring("Port", "Role: input, output, vcc, gnd", parent=self.root)
            if role:
                identifier = self.next_id("P")
                add_port(self.session, identifier, role.strip().lower())
                self.refresh(identifier)

        def value(self):
            identifier = self.selected().split(".")[0]
            component = next((c for c in self.session["candidate"]["components"] if c["id"] == identifier), None)
            require(component is not None and component["part"] in ("resistor", "capacitor"),
                    "select a resistor/capacitor endpoint")
            value = simpledialog.askfloat("Value", "Positive SI value (ohms or farads):", minvalue=0, parent=self.root)
            if value is not None:
                require(value > 0, "value must be positive")
                component.update(value_si=value, value_confirmed=False)
                invalidate(self.session)
                self.refresh()

        def remove(self):
            identifier = self.selected().split(".")[0]
            if messagebox.askyesno("Remove object", f"Remove {identifier} and all its endpoints?", parent=self.root):
                remove_item(self.session, identifier)
                self.refresh()

        def hidden(self):
            target = self.selected()
            annotate(self.session, target, visible=False)
            self.refresh(target)

        def save_json(self, value, filename):
            destination = filedialog.asksaveasfilename(parent=self.root, defaultextension=".json",
                initialfile=filename, filetypes=[("JSON", "*.json")])
            if destination:
                Path(destination).write_text(json.dumps(value, indent=2, allow_nan=False) + "\n", encoding="utf-8")
                self.status.set("Saved " + destination)
            return destination

        def save(self):
            self.save_json(self.session, source.stem + ".annotations.json")
            self.save_json(self.session["board"], source.stem + ".board.json")

        def export_candidate(self):
            self.save_json(candidate_from_session(self.session), source.stem + ".candidate.json")

        def export_labels(self):
            require(self.board_ack.get() and self.review_ack.get(), "complete both review acknowledgments")
            self.save_json(training_record(self.session, reviewed=True), source.stem + ".labels.json")

        def export_netlist(self):
            require(self.board_ack.get() and self.review_ack.get(), "complete both review acknowledgments")
            candidate = candidate_from_session(self.session)
            candidate = confirm(candidate, self.session["board"], candidate["revision"])
            netlist = compile_netlist(candidate, self.session["board"])
            self.save_json(netlist, source.stem + ".netlist.json")

    app = Annotator()
    app.root.mainloop()
