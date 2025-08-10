import os
from re import A
import threading
import time
import json
import tkinter as tk
from tkinter import ttk, messagebox, simpledialog, filedialog
from PIL import Image, ImageTk
import pyautogui
from screenshot import select_region


IMAGES_DIR_NAME = "images"


def ensure_images_dir() -> str:
    base_dir = os.path.dirname(os.path.abspath(__file__))
    images_dir = os.path.join(base_dir, IMAGES_DIR_NAME)
    os.makedirs(images_dir, exist_ok=True)
    return images_dir


def capture_region_to_file(filename_stem: str) -> str | None:
    images_dir = ensure_images_dir()
    file_name = filename_stem if filename_stem.lower().endswith(".png") else f"{filename_stem}.png"
    save_path = os.path.join(images_dir, file_name)

    region = select_region()
    if not region:
        return None
    pyautogui.screenshot(region=tuple(region)).save(save_path)
    return save_path


def try_locate_on_screen(image_path: str, confidence: float | None = None):
    """Locate using a PIL image object to avoid cv2 imread issues with non-ASCII paths."""
    kwargs = {}
    if confidence is not None:
        try:
            import cv2  # noqa: F401
            kwargs["confidence"] = confidence
        except Exception:
            # confidence param requires OpenCV; if not available, ignore it
            pass
    try:
        with Image.open(image_path) as needle_img:
            return pyautogui.locateOnScreen(needle_img, **kwargs)
    except Exception:
        return None


def click_image(image_path: str, move_duration: float = 0.15, confidence: float | None = None) -> bool:
    box = try_locate_on_screen(image_path, confidence)
    if not box:
        return False
    center = pyautogui.center(box)
    print(center)
    pyautogui.click(center.x, center.y)
    time.sleep(move_duration)
    return True


def wait_for_appear(image_path: str, timeout_sec: float = 30.0, poll_sec: float = 0.5, confidence: float | None = None) -> bool:
    end_time = time.time() + timeout_sec
    while time.time() < end_time:
        if try_locate_on_screen(image_path, confidence):
            return True
        time.sleep(poll_sec)
    return False


def wait_for_disappear(image_path: str, timeout_sec: float = 30.0, poll_sec: float = 0.5, confidence: float | None = None) -> bool:
    end_time = time.time() + timeout_sec
    while time.time() < end_time:
        if not try_locate_on_screen(image_path, confidence):
            return True
        time.sleep(poll_sec)
    return False


class ImageRecognitionMacroApp(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("Image Recognition Macro Helper")
        self.geometry("900x700")

        self.selected_image_path: str | None = None
        self.preview_photo: ImageTk.PhotoImage | None = None
        # Çoklu fonksiyon desteği: her fonksiyon kendi adım listesine sahiptir
        self.functions: dict[str, list[dict]] = {"Varsayılan": []}
        self.current_func_name: str = "Varsayılan"
        self.steps: list[dict] = self.functions[self.current_func_name]

        self._build_ui()

    def _build_ui(self) -> None:
        main = ttk.Frame(self, padding=12)
        main.pack(fill=tk.BOTH, expand=True)

        # Dosya adı
        row1 = ttk.Frame(main)
        row1.pack(fill=tk.X, pady=(0, 8))
        ttk.Label(row1, text="Dosya adı:").pack(side=tk.LEFT)
        self.name_var = tk.StringVar()
        name_entry = ttk.Entry(row1, textvariable=self.name_var)
        name_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=8)

        # Bölge Seç
        row2 = ttk.Frame(main)
        row2.pack(fill=tk.X, pady=(0, 8))
        self.select_btn = ttk.Button(row2, text="Bölge Seç", command=self.on_select_region)
        self.select_btn.pack(side=tk.LEFT)

        # Önizleme
        ttk.Label(main, text="Önizleme:").pack(anchor=tk.W)
        self.preview_label = ttk.Label(main)
        self.preview_label.pack(fill=None, expand=False, pady=(4, 12))

        # Adım Ekleme Alanı
        steps_frame = ttk.LabelFrame(main, text="Adımlar")
        steps_frame.pack(fill=tk.BOTH, expand=True, pady=(4, 8))

        # Fonksiyon seçimi ve yönetimi
        func_row = ttk.Frame(steps_frame)
        func_row.pack(fill=tk.X, pady=(6, 6))
        ttk.Label(func_row, text="Fonksiyon:").pack(side=tk.LEFT)
        self.func_var = tk.StringVar(value=self.current_func_name)
        self.func_combo = ttk.Combobox(func_row, textvariable=self.func_var, state="readonly", width=28)
        self.func_combo.pack(side=tk.LEFT, padx=(6, 6))
        self._refresh_function_combo()
        self.func_combo.bind("<<ComboboxSelected>>", self.on_function_selected)
        ttk.Button(func_row, text="Oluştur", command=self.create_function).pack(side=tk.LEFT)
        ttk.Button(func_row, text="Yeniden Adlandır", command=self.rename_function).pack(side=tk.LEFT, padx=(6, 0))
        ttk.Button(func_row, text="Sil", command=self.delete_function).pack(side=tk.LEFT, padx=(6, 0))
        ttk.Separator(func_row, orient=tk.VERTICAL).pack(side=tk.LEFT, fill=tk.Y, padx=8)
        ttk.Button(func_row, text="Botu Kaydet", command=self.save_bot).pack(side=tk.LEFT)
        ttk.Button(func_row, text="Botu Yükle", command=self.load_bot).pack(side=tk.LEFT, padx=(6, 0))

        form = ttk.Frame(steps_frame)
        form.pack(fill=tk.X, pady=(8, 4))

        # İşlem türü
        ttk.Label(form, text="İşlem:").grid(row=0, column=0, sticky=tk.W, padx=(0, 6))
        self.new_op_var = tk.StringVar(value="Resme Tıkla")
        self.new_op_combo = ttk.Combobox(
            form,
            textvariable=self.new_op_var,
            values=[
                "Resme Tıkla",
                "Resmin Kaybolmasını Bekle",
                "Resmin Görünmesini Bekle",
                "Fonksiyon Çağır",
                "Değişken Ata",
                "Eğer",
            ],
            state="readonly",
            width=28,
        )
        self.new_op_combo.grid(row=0, column=1, sticky=tk.W)

        # Görsel seçimi (./images)
        self.image_label = ttk.Label(form, text="Görsel:")
        self.image_label.grid(row=0, column=2, sticky=tk.W, padx=(16, 6))
        self.new_image_var = tk.StringVar()
        self.new_image_combo = ttk.Combobox(form, textvariable=self.new_image_var, width=40)
        self.new_image_combo.grid(row=0, column=3, sticky=tk.W)
        self.image_refresh_btn = ttk.Button(form, text="Yenile", command=self.refresh_images_list)
        self.image_refresh_btn.grid(row=0, column=4, padx=(6, 0))

        # Çağrılacak fonksiyon
        self.call_func_label = ttk.Label(form, text="Fonksiyon:")
        self.call_func_label.grid(row=0, column=5, sticky=tk.W, padx=(16, 6))
        self.new_call_func_var = tk.StringVar()
        self.new_call_func_combo = ttk.Combobox(form, textvariable=self.new_call_func_var, width=24, state="readonly")
        self.new_call_func_combo.grid(row=0, column=6, sticky=tk.W)
        self._refresh_call_func_combo()

        # Değişken/Koşul alanları
        self.var_name_label = ttk.Label(form, text="Değişken:")
        self.new_var_name_var = tk.StringVar()
        self.new_var_name_entry = ttk.Entry(form, textvariable=self.new_var_name_var, width=18)

        self.var_type_label = ttk.Label(form, text="Tür:")
        self.new_var_type_var = tk.StringVar(value="int")
        self.new_var_type_combo = ttk.Combobox(form, textvariable=self.new_var_type_var, values=["int", "bool", "string"], state="readonly", width=8)

        self.var_value_label = ttk.Label(form, text="Değer:")
        self.new_var_value_var = tk.StringVar()
        self.new_var_value_entry = ttk.Entry(form, textvariable=self.new_var_value_var, width=18)

        self.cmp_label = ttk.Label(form, text="Koşul:")
        self.new_cmp_var = tk.StringVar(value="==")
        self.new_cmp_combo = ttk.Combobox(form, textvariable=self.new_cmp_var, values=["==", "!="], state="readonly", width=6)

        # Varsayılan grid konumları (gizli başlayacak)
        self.var_name_label.grid(row=3, column=0, sticky=tk.W, pady=(6, 0))
        self.new_var_name_entry.grid(row=3, column=1, sticky=tk.W, padx=(6, 0), pady=(6, 0))
        self.var_type_label.grid(row=3, column=2, sticky=tk.W, padx=(16, 6), pady=(6, 0))
        self.new_var_type_combo.grid(row=3, column=3, sticky=tk.W, pady=(6, 0))
        self.var_value_label.grid(row=3, column=4, sticky=tk.W, padx=(16, 6), pady=(6, 0))
        self.new_var_value_entry.grid(row=3, column=5, sticky=tk.W, pady=(6, 0))
        self.cmp_label.grid(row=3, column=6, sticky=tk.W, padx=(16, 6), pady=(6, 0))
        self.new_cmp_combo.grid(row=3, column=7, sticky=tk.W, pady=(6, 0))

        # Parametreler
        self.timeout_label = ttk.Label(form, text="Timeout(s):")
        self.timeout_label.grid(row=1, column=0, sticky=tk.W, padx=(0, 6), pady=(6, 0))
        self.new_timeout_var = tk.StringVar(value="30")
        self.timeout_entry = ttk.Entry(form, textvariable=self.new_timeout_var, width=8)
        self.timeout_entry.grid(row=1, column=1, sticky=tk.W, pady=(6, 0))

        self.conf_label = ttk.Label(form, text="Confidence(0-1):")
        self.conf_label.grid(row=1, column=2, sticky=tk.W, padx=(16, 6), pady=(6, 0))
        self.new_conf_var = tk.StringVar(value="")
        self.conf_entry = ttk.Entry(form, textvariable=self.new_conf_var, width=10)
        self.conf_entry.grid(row=1, column=3, sticky=tk.W, pady=(6, 0))

        self.move_label = ttk.Label(form, text="Move(ms):")
        self.move_label.grid(row=1, column=4, sticky=tk.W, padx=(16, 6), pady=(6, 0))
        self.new_move_var = tk.StringVar(value="150")
        self.move_entry = ttk.Entry(form, textvariable=self.new_move_var, width=8)
        self.move_entry.grid(row=1, column=5, sticky=tk.W, pady=(6, 0))

        # Polling aralığı
        self.poll_label = ttk.Label(form, text="Poll(s):")
        self.poll_label.grid(row=1, column=6, sticky=tk.W, padx=(16, 6), pady=(6, 0))
        self.new_poll_var = tk.StringVar(value="0.5")
        self.poll_entry = ttk.Entry(form, textvariable=self.new_poll_var, width=8)
        self.poll_entry.grid(row=1, column=7, sticky=tk.W, pady=(6, 0))

        # Dallanma: Başarılı / Başarısız sonraki adım (1-based index)
        ttk.Label(form, text="Başarılı→Adım#:").grid(row=2, column=0, sticky=tk.W, padx=(0, 6), pady=(8, 0))
        self.new_next_ok_var = tk.StringVar(value="")
        ttk.Entry(form, textvariable=self.new_next_ok_var, width=8).grid(row=2, column=1, sticky=tk.W, pady=(8, 0))

        ttk.Label(form, text="Başarısız→Adım#:").grid(row=2, column=2, sticky=tk.W, padx=(16, 6), pady=(8, 0))
        self.new_next_fail_var = tk.StringVar(value="")
        ttk.Entry(form, textvariable=self.new_next_fail_var, width=8).grid(row=2, column=3, sticky=tk.W, pady=(8, 0))

        # Adım listeleme
        list_frame = ttk.Frame(steps_frame)
        list_frame.pack(fill=tk.BOTH, expand=True, pady=(8, 4))
        cols = ("#", "İşlem", "Görsel", "Parametreler", "Başarılı→", "Başarısız→")
        self.tree = ttk.Treeview(list_frame, columns=cols, show="headings", height=8)
        for c, w in zip(cols, (40, 180, 260, 220, 90, 110)):
            self.tree.heading(c, text=c)
            self.tree.column(c, width=w, anchor=tk.W)
        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        ttk.Scrollbar(list_frame, orient=tk.VERTICAL, command=self.tree.yview).pack(side=tk.RIGHT, fill=tk.Y)
        self.tree.configure(yscrollcommand=lambda f, l: None)
        # Çift tıklama ile adım düzenleme
        self.tree.bind("<Double-1>", self.on_step_double_click)

        # Adım kontrol butonları
        ctrl = ttk.Frame(steps_frame)
        ctrl.pack(fill=tk.X)
        ttk.Button(ctrl, text="Adım Ekle", command=self.add_step).pack(side=tk.LEFT)
        ttk.Button(ctrl, text="Seçileni Sil", command=self.remove_selected_step).pack(side=tk.LEFT, padx=(6, 0))
        ttk.Button(ctrl, text="Yukarı", command=lambda: self.move_step(-1)).pack(side=tk.LEFT, padx=(6, 0))
        ttk.Button(ctrl, text="Aşağı", command=lambda: self.move_step(1)).pack(side=tk.LEFT, padx=(6, 0))
        ttk.Button(ctrl, text="Temizle", command=self.clear_steps).pack(side=tk.LEFT, padx=(6, 0))

        # İşlem türü değişince form görünürlüğünü güncelle (tüm widget'lar oluşturulduktan sonra bağla)
        self.new_op_combo.bind("<<ComboboxSelected>>", lambda _e=None: self._update_add_form_visibility())
        self._update_add_form_visibility()

        # Başlat
        self.start_btn = ttk.Button(main, text="Makroyu Başlat", command=self.on_start_macro)
        self.start_btn.pack(pady=(4, 8))

        # Durum
        self.status_var = tk.StringVar(value="Hazır")
        ttk.Label(main, textvariable=self.status_var).pack(anchor=tk.W)

    def set_status(self, text: str) -> None:
        self.status_var.set(text)
        self.update_idletasks()

    # --- Fonksiyon yönetimi ---
    def _refresh_function_combo(self) -> None:
        self.func_combo["values"] = list(self.functions.keys())
        self.func_var.set(self.current_func_name)
        self._refresh_call_func_combo()

    def _refresh_call_func_combo(self) -> None:
        # Fill call-func combobox with available function names
        if hasattr(self, "new_call_func_combo"):
            self.new_call_func_combo["values"] = list(self.functions.keys())
            if self.current_func_name and not self.new_call_func_var.get():
                self.new_call_func_var.set(self.current_func_name)

    def on_function_selected(self, _event=None) -> None:
        name = self.func_var.get()
        if name in self.functions:
            self.current_func_name = name
            self.steps = self.functions[self.current_func_name]
            self._sync_steps_tree()

    def create_function(self) -> None:
        name = simpledialog.askstring("Fonksiyon Oluştur", "Fonksiyon adı:", parent=self)
        if not name:
            return
        name = name.strip()
        if not name:
            return
        if name in self.functions:
            messagebox.showwarning("Uyarı", "Bu ad zaten var.")
            return
        self.functions[name] = []
        self.current_func_name = name
        self.steps = self.functions[self.current_func_name]
        self._refresh_function_combo()
        self._sync_steps_tree()

    def rename_function(self) -> None:
        old = self.current_func_name
        name = simpledialog.askstring("Yeniden Adlandır", "Yeni ad:", initialvalue=old, parent=self)
        if not name:
            return
        name = name.strip()
        if not name or name == old:
            return
        if name in self.functions:
            messagebox.showwarning("Uyarı", "Bu ad zaten var.")
            return
        self.functions[name] = self.functions.pop(old)
        self.current_func_name = name
        self._refresh_function_combo()
        self._sync_steps_tree()

    def delete_function(self) -> None:
        if len(self.functions) <= 1:
            messagebox.showwarning("Uyarı", "Son fonksiyonu silemezsiniz.")
            return
        if not messagebox.askyesno("Onay", f"'{self.current_func_name}' fonksiyonu silinsin mi?"):
            return
        del self.functions[self.current_func_name]
        self.current_func_name = list(self.functions.keys())[0]
        self.steps = self.functions[self.current_func_name]
        self._refresh_function_combo()
        self._sync_steps_tree()

    def on_select_region(self) -> None:
        name = self.name_var.get().strip()
        if not name:
            messagebox.showwarning("Uyarı", "Lütfen bir dosya adı girin.")
            return

        images_dir = ensure_images_dir()
        file_name = name if name.lower().endswith(".png") else f"{name}.png"
        target_path = os.path.join(images_dir, file_name)
        if os.path.exists(target_path):
            messagebox.showwarning("Uyarı", "Bu dosya adı zaten mevcut.")
            return

        self.set_status("Bölge seçin... (ESC iptal)")
        saved_path = capture_region_to_file(name)
        if not saved_path:
            self.set_status("İptal edildi.")
            return

        self.selected_image_path = saved_path
        self._load_preview(saved_path)
        self.set_status(f"Kaydedildi: ./{IMAGES_DIR_NAME}/{os.path.basename(saved_path)}")

    def _load_preview(self, image_path: str) -> None:
        try:
            with Image.open(image_path) as img:
                img = img.copy()
            img.thumbnail((280, 280), Image.LANCZOS)
            self.preview_photo = ImageTk.PhotoImage(img)
            self.preview_label.configure(image=self.preview_photo)
        except Exception as e:
            messagebox.showerror("Önizleme Hatası", f"Görüntü yüklenemedi:\n{e}")

    def on_start_macro(self) -> None:
        if not self.steps:
            messagebox.showwarning("Uyarı", "Lütfen en az bir adım ekleyin.")
            return
        self.set_status("Makro çalışıyor...")
        self._set_buttons_state(disabled=True)
        threading.Thread(target=self._run_macro_safe, args=(self.steps,), daemon=True).start()

    def _set_buttons_state(self, disabled: bool) -> None:
        state = tk.DISABLED if disabled else tk.NORMAL
        self.select_btn.configure(state=state)
        self.start_btn.configure(state=state)

    def _run_macro(self, steps: list[dict]) -> None:
        try:
            idx = 1
            while 1 <= idx <= len(steps):
                step = steps[idx - 1]
                op = step["op"]
                image_path = step["image"]
                confidence = step.get("confidence")
                timeout = step.get("timeout_sec", 30.0)
                poll = step.get("poll_sec", 0.5)
                move_ms = step.get("move_ms", 150)
                next_ok = step.get("next_ok")
                next_fail = step.get("next_fail")

                if op == "Resme Tıkla":
                    self._thread_status(f"[{idx}] Resme tıkla: {os.path.basename(image_path)}")
                    ok = click_image(
                        image_path,
                        move_duration=max(0.0, float(move_ms) / 1000.0),
                        confidence=confidence,
                    )
                elif op == "Resmin Kaybolmasını Bekle":
                    self._thread_status(f"[{idx}] Kaybolmasını bekle: {os.path.basename(image_path)}")
                    ok = wait_for_disappear(
                        image_path,
                        timeout_sec=float(timeout),
                        poll_sec=float(poll),
                        confidence=confidence,
                    )
                elif op == "Resmin Görünmesini Bekle":
                    self._thread_status(f"[{idx}] Görünmesini bekle: {os.path.basename(image_path)}")
                    ok = wait_for_appear(
                        image_path,
                        timeout_sec=float(timeout),
                        poll_sec=float(poll),
                        confidence=confidence,
                    )
                elif op == "Fonksiyon Çağır":
                    func_name = step.get("call_func")
                    self._thread_status(f"[{idx}] Fonksiyon çağır: {func_name}")
                    ok = self._run_sub_function(func_name)
                elif op == "Değişken Ata":
                    ok = self._exec_set_var(step)
                elif op == "Eğer":
                    ok = self._exec_if(step)
                else:
                    self._thread_status(f"[{idx}] Bilinmeyen işlem: {op}")
                    ok = False

                # Dallanma mantığı: next_ok / next_fail (1-based). Boşsa sıradaki adıma geç.
                if ok:
                    if next_ok:
                        try:
                            idx = int(next_ok)
                            continue
                        except ValueError:
                            pass
                    idx += 1
                else:
                    if next_fail:
                        try:
                            idx = int(next_fail)
                            continue
                        except ValueError:
                            pass
                    idx += 1

            self._thread_status("Makro tamamlandı.")
        except Exception as e:
            self._thread_status(f"Hata: {e}")
        finally:
            self.after(0, lambda: self._set_buttons_state(disabled=False))

    def _run_macro_safe(self, steps: list[dict]) -> None:
        try:
            self._run_macro(steps)
        except Exception as e:
            self._thread_status(f"Hata: {e}")

    def _thread_status(self, text: str) -> None:
        self.after(0, lambda t=text: self.set_status(t))

    def _run_sub_function(self, name: str | None) -> bool:
        # None or unknown → fail
        if not name or name not in self.functions:
            return False
        steps = self.functions.get(name, [])
        # Alt fonksiyonda dallanma kendi içinde çalışır, bitince True döndürür
        try:
            idx = 1
            while 1 <= idx <= len(steps):
                step = steps[idx - 1]
                op = step["op"]
                image_path = step.get("image", "")
                confidence = step.get("confidence")
                timeout = step.get("timeout_sec", 30.0)
                poll = step.get("poll_sec", 0.5)
                move_ms = step.get("move_ms", 150)
                next_ok = step.get("next_ok")
                next_fail = step.get("next_fail")

                if op == "Resme Tıkla":
                    ok = click_image(image_path, move_duration=max(0.0, float(move_ms) / 1000.0), confidence=confidence)
                elif op == "Resmin Kaybolmasını Bekle":
                    ok = wait_for_disappear(image_path, timeout_sec=float(timeout), poll_sec=float(poll), confidence=confidence)
                elif op == "Resmin Görünmesini Bekle":
                    ok = wait_for_appear(image_path, timeout_sec=float(timeout), poll_sec=float(poll), confidence=confidence)
                elif op == "Fonksiyon Çağır":
                    ok = self._run_sub_function(step.get("call_func"))
                elif op == "Değişken Ata":
                    ok = self._exec_set_var(step)
                elif op == "Eğer":
                    ok = self._exec_if(step)
                else:
                    ok = False

                if ok:
                    if next_ok:
                        try:
                            idx = int(next_ok)
                            continue
                        except ValueError:
                            pass
                    idx += 1
                else:
                    if next_fail:
                        try:
                            idx = int(next_fail)
                            continue
                        except ValueError:
                            pass
                    idx += 1
            return True
        except Exception:
            return False

    # --- Variables ---
    def _parse_value(self, value_str: str, value_type: str):
        t = (value_type or "string").lower()
        if t == "int":
            try:
                return int(value_str)
            except Exception:
                return 0
        if t == "bool":
            return str(value_str).strip().lower() in ("1", "true", "yes", "on")
        return str(value_str)

    def _exec_set_var(self, step: dict) -> bool:
        name = step.get("var_name", "").strip()
        if not name:
            return False
        value = self._parse_value(step.get("var_value", ""), step.get("var_type", "string"))
        if not hasattr(self, "variables"):
            self.variables = {}

        if "+=" in value:
            value = value.replace("+=", "")
            self.variables[name] += int(value)
        else:
            self.variables[name] = value
        self._thread_status(f"Değişken ata: {name} = {value}")
        return True

    def _exec_if(self, step: dict) -> bool:
        name = step.get("var_name", "").strip()
        if not hasattr(self, "variables"):
            self.variables = {}
        left = self.variables.get(name)
        right = self._parse_value(step.get("var_value", ""), step.get("var_type", "string"))
        cmp_op = step.get("cmp", "==")
        result = (left == right) if cmp_op == "==" else (left != right)
        self._thread_status(f"Eğer: {name} {cmp_op} {right} → {result}")
        return result

    # --- Steps helpers ---
    def refresh_images_list(self) -> None:
        images_dir = ensure_images_dir()
        files = sorted([f for f in os.listdir(images_dir) if f.lower().endswith((".png", ".jpg", ".jpeg"))])
        self.new_image_combo["values"] = files
        if files and not self.new_image_var.get():
            self.new_image_var.set(files[0])

    def add_step(self) -> None:
        img_name = self.new_image_var.get().strip()
        op_name = self.new_op_var.get()
        if op_name in ("Resme Tıkla", "Resmin Kaybolmasını Bekle", "Resmin Görünmesini Bekle"):
            if not img_name:
                messagebox.showwarning("Uyarı", "Lütfen ./images içinden bir görsel seçin.")
                return
        images_dir = ensure_images_dir()
        img_path = os.path.join(images_dir, img_name) if img_name else ""
        if op_name in ("Resme Tıkla", "Resmin Kaybolmasını Bekle", "Resmin Görünmesini Bekle"):
            if not os.path.exists(img_path):
                messagebox.showwarning("Uyarı", "Seçilen görsel bulunamadı.")
                return
        elif op_name == "Fonksiyon Çağır":
            call_name = self.new_call_func_var.get().strip()
            if not call_name or call_name not in self.functions:
                messagebox.showwarning("Uyarı", "Geçerli bir fonksiyon seçin.")
                return

        # Parse params
        try:
            timeout = float(self.new_timeout_var.get() or 30)
        except ValueError:
            timeout = 30.0
        try:
            move_ms = int(self.new_move_var.get() or 150)
        except ValueError:
            move_ms = 150
        try:
            poll_val = float(self.new_poll_var.get() or 0.5)
        except ValueError:
            poll_val = 0.5
        try:
            conf = float(self.new_conf_var.get()) if self.new_conf_var.get() != "" else None
        except ValueError:
            conf = None

        step = {"op": op_name}
        # Ortak dallanma alanları
        step["next_ok"] = self.new_next_ok_var.get().strip() or None
        step["next_fail"] = self.new_next_fail_var.get().strip() or None

        if op_name in ("Resme Tıkla", "Resmin Kaybolmasını Bekle", "Resmin Görünmesini Bekle"):
            step.update({
                "image": img_path,
                "timeout_sec": timeout,
                "poll_sec": poll_val,
                "move_ms": move_ms,
                "confidence": conf,
            })
        elif op_name == "Fonksiyon Çağır":
            step["call_func"] = call_name
        elif op_name in ("Değişken Ata", "Eğer"):
            step["var_name"] = self.new_var_name_var.get().strip()
            step["var_type"] = self.new_var_type_var.get()
            step["var_value"] = self.new_var_value_var.get()
            if op_name == "Eğer":
                step["cmp"] = self.new_cmp_var.get()
        if op_name == "Fonksiyon Çağır":
            step["call_func"] = call_name
        self.steps.append(step)
        self._sync_steps_tree()
        # Temizle
        self.new_var_name_var.set("")
        self.new_var_value_var.set("")

    def _update_add_form_visibility(self) -> None:
        op_name = self.new_op_var.get()
        if op_name == "Fonksiyon Çağır":
            # Hide image widgets
            self.image_label.grid_remove()
            self.new_image_combo.grid_remove()
            self.image_refresh_btn.grid_remove()
            # Show function widgets
            self.new_call_func_var.set(self.current_func_name)
            self._refresh_call_func_combo()
            self.call_func_label.grid(row=0, column=5, sticky=tk.W, padx=(16, 6))
            self.new_call_func_combo.grid(row=0, column=6, sticky=tk.W)
            # Hide variable widgets
            self.var_name_label.grid_remove()
            self.new_var_name_entry.grid_remove()
            self.var_type_label.grid_remove()
            self.new_var_type_combo.grid_remove()
            self.var_value_label.grid_remove()
            self.new_var_value_entry.grid_remove()
            self.cmp_label.grid_remove()
            self.new_cmp_combo.grid_remove()
            # Hide timing/locate params for function call
            self.timeout_label.grid_remove()
            self.timeout_entry.grid_remove()
            self.conf_label.grid_remove()
            self.conf_entry.grid_remove()
            self.move_label.grid_remove()
            self.move_entry.grid_remove()
            self.poll_label.grid_remove()
            self.poll_entry.grid_remove()
        elif op_name in ("Resme Tıkla", "Resmin Kaybolmasını Bekle", "Resmin Görünmesini Bekle"):
            # Show image widgets
            self.image_label.grid(row=0, column=2, sticky=tk.W, padx=(16, 6))
            self.new_image_combo.grid(row=0, column=3, sticky=tk.W)
            self.image_refresh_btn.grid(row=0, column=4, padx=(6, 0))
            # Hide function widgets
            self.call_func_label.grid_remove()
            self.new_call_func_combo.grid_remove()
            # Hide variable widgets
            self.var_name_label.grid_remove()
            self.new_var_name_entry.grid_remove()
            self.var_type_label.grid_remove()
            self.new_var_type_combo.grid_remove()
            self.var_value_label.grid_remove()
            self.new_var_value_entry.grid_remove()
            self.cmp_label.grid_remove()
            self.new_cmp_combo.grid_remove()
            # Show timing/locate params
            self.timeout_label.grid(row=1, column=0, sticky=tk.W, padx=(0, 6), pady=(6, 0))
            self.timeout_entry.grid(row=1, column=1, sticky=tk.W, pady=(6, 0))
            self.conf_label.grid(row=1, column=2, sticky=tk.W, padx=(16, 6), pady=(6, 0))
            self.conf_entry.grid(row=1, column=3, sticky=tk.W, pady=(6, 0))
            self.move_label.grid(row=1, column=4, sticky=tk.W, padx=(16, 6), pady=(6, 0))
            self.move_entry.grid(row=1, column=5, sticky=tk.W, pady=(6, 0))
            self.poll_label.grid(row=1, column=6, sticky=tk.W, padx=(16, 6), pady=(6, 0))
            self.poll_entry.grid(row=1, column=7, sticky=tk.W, pady=(6, 0))
        else:
            # Variable/Condition widgets visible
            self.var_name_label.grid(row=3, column=0, sticky=tk.W, pady=(6, 0))
            self.new_var_name_entry.grid(row=3, column=1, sticky=tk.W, padx=(6, 0), pady=(6, 0))
            self.var_type_label.grid(row=3, column=2, sticky=tk.W, padx=(16, 6), pady=(6, 0))
            self.new_var_type_combo.grid(row=3, column=3, sticky=tk.W, pady=(6, 0))
            self.var_value_label.grid(row=3, column=4, sticky=tk.W, padx=(16, 6), pady=(6, 0))
            self.new_var_value_entry.grid(row=3, column=5, sticky=tk.W, pady=(6, 0))
            if op_name == "Eğer":
                self.cmp_label.grid(row=3, column=6, sticky=tk.W, padx=(16, 6), pady=(6, 0))
                self.new_cmp_combo.grid(row=3, column=7, sticky=tk.W, pady=(6, 0))
            else:
                self.cmp_label.grid_remove()
                self.new_cmp_combo.grid_remove()
            # Hide image/function widgets
            self.image_label.grid_remove()
            self.new_image_combo.grid_remove()
            self.image_refresh_btn.grid_remove()
            self.call_func_label.grid_remove()
            self.new_call_func_combo.grid_remove()
            # Hide timing/locate params for variable ops
            self.timeout_label.grid_remove()
            self.timeout_entry.grid_remove()
            self.conf_label.grid_remove()
            self.conf_entry.grid_remove()
            self.move_label.grid_remove()
            self.move_entry.grid_remove()
            self.poll_label.grid_remove()
            self.poll_entry.grid_remove()

    # --- Kaydet/Yükle ---
    def _export_state(self) -> dict:
        # Save functions with image paths relative to ./images
        images_dir = ensure_images_dir()
        data_funcs: dict[str, list[dict]] = {}
        for fname, steps in self.functions.items():
            out_steps: list[dict] = []
            for s in steps:
                out_steps.append(s)
            data_funcs[fname] = out_steps
        return {
            "current_func": self.current_func_name,
            "functions": data_funcs,
        }

    def _import_state(self, data: dict) -> None:
        images_dir = ensure_images_dir()
        new_functions: dict[str, list[dict]] = {}
        for fname, steps in data.get("functions", {}).items():
            restored: list[dict] = []
            for s in steps or []:
                restored.append(s)
            new_functions[fname] = restored

        self.functions = new_functions or {"Varsayılan": []}
        desired = data.get("current_func")
        self.current_func_name = desired if desired in self.functions else list(self.functions.keys())[0]
        self.steps = self.functions[self.current_func_name]
        self._refresh_function_combo()
        self._sync_steps_tree()

    def save_bot(self) -> None:
        try:
            default_name = "macro_bot.json"
            path = filedialog.asksaveasfilename(
                parent=self,
                title="Botu Kaydet",
                defaultextension=".json",
                filetypes=[("JSON", "*.json")],
                initialfile=default_name,
            )
            if not path:
                return
            data = self._export_state()
            with open(path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            self.set_status(f"Kaydedildi: {os.path.basename(path)}")
        except Exception as e:
            messagebox.showerror("Kaydetme Hatası", f"Kaydedilemedi:\n{e}")

    def load_bot(self) -> None:
        try:
            path = filedialog.askopenfilename(
                parent=self,
                title="Botu Yükle",
                filetypes=[("JSON", "*.json")],
            )
            if not path:
                return
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            self._import_state(data)
            self.set_status(f"Yüklendi: {os.path.basename(path)}")
        except Exception as e:
            messagebox.showerror("Yükleme Hatası", f"Yüklenemedi:\n{e}")

    # Adım düzenleme (çift tık)
    def on_step_double_click(self, _event=None) -> None:
        sel = self.tree.selection()
        if not sel:
            return
        index = int(self.tree.item(sel[0], "values")[0]) - 1
        if 0 <= index < len(self.steps):
            self._edit_step_dialog(index)

    def _edit_step_dialog(self, index: int) -> None:
        step = self.steps[index]

        win = tk.Toplevel(self)
        win.title(f"Adımı Düzenle #{index + 1}")
        win.transient(self)
        win.grab_set()

        frm = ttk.Frame(win, padding=12)
        frm.pack(fill=tk.BOTH, expand=True)

        # İşlem
        ttk.Label(frm, text="İşlem:").grid(row=0, column=0, sticky=tk.W)
        op_var = tk.StringVar(value=step.get("op", "Resme Tıkla"))
        op_combo = ttk.Combobox(frm, textvariable=op_var, values=["Resme Tıkla", "Resmin Kaybolmasını Bekle", "Resmin Görünmesini Bekle", "Fonksiyon Çağır", "Değişken Ata", "Eğer"], state="readonly")
        op_combo.grid(row=0, column=1, sticky=tk.W, padx=(6, 0))

        # Görsel
        
        ttk.Label(frm, text="Görsel:").grid(row=1, column=0, sticky=tk.W, pady=(8, 0))
        img_var = tk.StringVar(value=os.path.basename(step.get("image", "")))
        img_combo = ttk.Combobox(frm, textvariable=img_var, width=40)
        img_combo.grid(row=1, column=1, sticky=tk.W, padx=(6, 0), pady=(8, 0))
        # Doldur
        images_dir = ensure_images_dir()
        files = sorted([f for f in os.listdir(images_dir) if f.lower().endswith((".png", ".jpg", ".jpeg"))])
        img_combo["values"] = files

        # Çağrılacak fonksiyon
        ttk.Label(frm, text="Fonksiyon:").grid(row=1, column=2, sticky=tk.W, pady=(8, 0))
        call_var = tk.StringVar(value=step.get("call_func") or "")
        call_combo = ttk.Combobox(frm, textvariable=call_var, values=list(self.functions.keys()), state="readonly", width=24)
        call_combo.grid(row=1, column=3, sticky=tk.W, padx=(6, 0), pady=(8, 0))

        def update_edit_visibility(*_a):
            if op_var.get() == "Fonksiyon Çağır":
                img_combo.grid_remove()
                call_combo.grid(row=1, column=3, sticky=tk.W, padx=(6, 0), pady=(8, 0))
            elif op_var.get() in ("Değişken Ata", "Eğer"):
                img_combo.grid_remove()
                call_combo.grid_remove()
            else:
                img_combo.grid(row=1, column=1, sticky=tk.W, padx=(6, 0), pady=(8, 0))
                call_combo.grid_remove()

        op_combo.bind("<<ComboboxSelected>>", update_edit_visibility)
        update_edit_visibility()

        # Parametreler
        ttk.Label(frm, text="Timeout(s):").grid(row=2, column=0, sticky=tk.W, pady=(8, 0))
        timeout_var = tk.StringVar(value=str(step.get("timeout_sec", 30)))
        ttk.Entry(frm, textvariable=timeout_var, width=10).grid(row=2, column=1, sticky=tk.W, padx=(6, 0), pady=(8, 0))

        ttk.Label(frm, text="Confidence(0-1):").grid(row=3, column=0, sticky=tk.W)
        conf_var = tk.StringVar(value=("" if step.get("confidence") is None else str(step.get("confidence"))))
        ttk.Entry(frm, textvariable=conf_var, width=10).grid(row=3, column=1, sticky=tk.W, padx=(6, 0))

        ttk.Label(frm, text="Poll(s):").grid(row=3, column=2, sticky=tk.W)
        poll_var = tk.StringVar(value=str(step.get("poll_sec", 0.5)))
        ttk.Entry(frm, textvariable=poll_var, width=10).grid(row=3, column=3, sticky=tk.W, padx=(6, 0))

        ttk.Label(frm, text="Move(ms):").grid(row=4, column=0, sticky=tk.W)
        move_var = tk.StringVar(value=str(step.get("move_ms", 150)))
        ttk.Entry(frm, textvariable=move_var, width=10).grid(row=4, column=1, sticky=tk.W, padx=(6, 0))

        # Variable widgets in edit dialog
        ttk.Label(frm, text="Değişken:").grid(row=5, column=0, sticky=tk.W, pady=(8, 0))
        e_var_name = tk.StringVar(value=step.get("var_name", ""))
        ttk.Entry(frm, textvariable=e_var_name, width=18).grid(row=5, column=1, sticky=tk.W, padx=(6, 0), pady=(8, 0))

        ttk.Label(frm, text="Tür:").grid(row=5, column=2, sticky=tk.W, padx=(16, 6), pady=(8, 0))
        e_var_type = tk.StringVar(value=step.get("var_type", "int"))
        ttk.Combobox(frm, textvariable=e_var_type, values=["int", "bool", "string"], state="readonly", width=8).grid(row=5, column=3, sticky=tk.W, pady=(8, 0))

        ttk.Label(frm, text="Değer:").grid(row=5, column=4, sticky=tk.W, padx=(16, 6), pady=(8, 0))
        e_var_value = tk.StringVar(value=str(step.get("var_value", "")))
        ttk.Entry(frm, textvariable=e_var_value, width=18).grid(row=5, column=5, sticky=tk.W, pady=(8, 0))

        ttk.Label(frm, text="Koşul:").grid(row=5, column=6, sticky=tk.W, padx=(16, 6), pady=(8, 0))
        e_cmp = tk.StringVar(value=step.get("cmp", "=="))
        ttk.Combobox(frm, textvariable=e_cmp, values=["==", "!="], state="readonly", width=6).grid(row=5, column=7, sticky=tk.W, pady=(8, 0))

        ttk.Label(frm, text="Başarılı→Adım#:").grid(row=6, column=0, sticky=tk.W, pady=(8, 0))
        next_ok_var = tk.StringVar(value=step.get("next_ok") or "")
        ttk.Entry(frm, textvariable=next_ok_var, width=10).grid(row=6, column=1, sticky=tk.W, padx=(6, 0), pady=(8, 0))

        ttk.Label(frm, text="Başarısız→Adım#:").grid(row=7, column=0, sticky=tk.W)
        next_fail_var = tk.StringVar(value=step.get("next_fail") or "")
        ttk.Entry(frm, textvariable=next_fail_var, width=10).grid(row=7, column=1, sticky=tk.W, padx=(6, 0))

        btn_row = ttk.Frame(frm)
        btn_row.grid(row=8, column=0, columnspan=2, pady=(12, 0))
        def save_and_close():
            # Validate and update
            sel_img_name = img_var.get().strip()
            if op_var.get() != "Fonksiyon Çağır" and op_var.get() != "Değişken Ata" and op_var.get() != "Eğer":
                if not sel_img_name:
                    messagebox.showwarning("Uyarı", "Görsel adı boş olamaz.", parent=win)
                    return
                img_path = os.path.join(images_dir, sel_img_name)
                if not os.path.exists(img_path):
                    messagebox.showwarning("Uyarı", "Görsel bulunamadı.", parent=win)
                    return
            else:
                img_path = step.get("image", "")
            try:
                t_out = float(timeout_var.get() or 30)
            except ValueError:
                t_out = 30.0
            try:
                m_ms = int(move_var.get() or 150)
            except ValueError:
                m_ms = 150
            try:
                c_val = float(conf_var.get()) if conf_var.get() != "" else None
            except ValueError:
                c_val = None
            try:
                p_val = float(poll_var.get() or 0.5)
            except ValueError:
                p_val = 0.5

            updated = {
                "op": op_var.get(),
                "image": img_path,
                "timeout_sec": t_out,
                "move_ms": m_ms,
                "confidence": c_val,
                "poll_sec": p_val,
                "next_ok": next_ok_var.get().strip() or None,
                "next_fail": next_fail_var.get().strip() or None,
            }
            if op_var.get() == "Fonksiyon Çağır":
                updated["call_func"] = call_var.get().strip() or None
            else:
                updated.pop("call_func", None)
            if op_var.get() in ("Değişken Ata", "Eğer"):
                updated["var_name"] = e_var_name.get().strip()
                updated["var_type"] = e_var_type.get()
                updated["var_value"] = e_var_value.get()
                if op_var.get() == "Eğer":
                    updated["cmp"] = e_cmp.get()
            step.update(updated)
            self._sync_steps_tree()
            win.destroy()

        ttk.Button(btn_row, text="Kaydet", command=save_and_close).pack(side=tk.LEFT)
        ttk.Button(btn_row, text="İptal", command=win.destroy).pack(side=tk.LEFT, padx=(8, 0))

    def remove_selected_step(self) -> None:
        sel = self.tree.selection()
        if not sel:
            return
        index = int(self.tree.item(sel[0], "values")[0]) - 1
        if 0 <= index < len(self.steps):
            del self.steps[index]
            self._sync_steps_tree()

    def move_step(self, delta: int) -> None:
        sel = self.tree.selection()
        if not sel:
            return
        index = int(self.tree.item(sel[0], "values")[0]) - 1
        new_index = index + delta
        if 0 <= new_index < len(self.steps):
            self.steps[index], self.steps[new_index] = self.steps[new_index], self.steps[index]
            self._sync_steps_tree()
            self.tree.selection_set(self.tree.get_children()[new_index])

    def clear_steps(self) -> None:
        self.steps.clear()
        self._sync_steps_tree()

    def _sync_steps_tree(self) -> None:
        for i in self.tree.get_children():
            self.tree.delete(i)
        for idx, step in enumerate(self.steps, start=1):
            params = []
            if step["op"] == "Resme Tıkla":
                params.append(f"move={step.get('move_ms', 150)}ms")
            else:
                params.append(f"timeout={step.get('timeout_sec', 30)}s")
            if step.get("confidence") is not None:
                params.append(f"conf={step['confidence']}")
            if step["op"] == "Değişken Ata":
                self.tree.insert("", tk.END, values=(
                idx,
                step["op"],
                f"{step['var_type']} {step['var_name']} = {step['var_value']}",
                ", ".join(params),
                step.get("next_ok") or "",
                step.get("next_fail") or "",
                ))
            elif step["op"] == "Eğer":
                self.tree.insert("", tk.END, values=(
                    idx,
                    step["op"],
                    f"if {step['var_type']} {step['var_name']} {step['cmp']} {step['var_value']}",
                    ", ".join(params),
                    step.get("next_ok") or "",
                    step.get("next_fail") or "",
                ))
            elif step["op"] == "Fonksiyon Çağır":
                self.tree.insert("", tk.END, values=(
                    idx,
                    step["op"],
                    f" {step['call_func']}",
                    ", ".join(params),
                    step.get("next_ok") or "",
                    step.get("next_fail") or "",
                ))
            else:
                self.tree.insert("", tk.END, values=(
                    idx,
                    step["op"],
                    os.path.basename(step["image"]),
                    ", ".join(params),
                    step.get("next_ok") or "",
                    step.get("next_fail") or "",
                ))
        # Keep images list fresh
        self.refresh_images_list()


if __name__ == "__main__":
    # PyAutoGUI ayarları (isteğe bağlı)
    pyautogui.PAUSE = 0.1
    pyautogui.FAILSAFE = True

    app = ImageRecognitionMacroApp()
    app.mainloop()


