import tkinter as tk
from tkinter import filedialog, simpledialog, ttk, messagebox
from PIL import Image, ImageTk
import fitz  # PyMuPDF

class PDFAnnotator:
    def __init__(self, root):
        self.root = root
        self.root.title("PDF Annotator")
        self.root.geometry("1000x700")

        # PDF Variables
        self.pdf_path = None
        self.doc = None
        self.zoom_factor = 1.0

        # Annotation Variables
        self.current_tool = None
        self.text_color = (0, 0, 0)  # Default: Black
        self.drawing = False
        self.last_x, self.last_y = None, None
        self.annotations = []  # Store drawn elements for persistence

        # Main Frame (Resizable)
        self.frame = tk.Frame(root)
        self.frame.pack(fill=tk.BOTH, expand=True)

        # Canvas for PDF Display
        self.canvas = tk.Canvas(self.frame, bg="white")
        self.canvas.pack(fill=tk.BOTH, expand=True)

        # Scrollbars
        self.v_scroll = tk.Scrollbar(self.frame, orient=tk.VERTICAL, command=self.canvas.yview)
        self.v_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self.canvas.config(yscrollcommand=self.v_scroll.set)

        # Bind Events
        self.canvas.bind("<Button-1>", self.start_annotation)
        self.canvas.bind("<B1-Motion>", self.continue_annotation)
        self.canvas.bind("<ButtonRelease-1>", self.stop_drawing)
        self.canvas.bind("<MouseWheel>", self.scroll_canvas)  # Bind mouse wheel for smooth scrolling

        # Toolbar for Controls
        self.toolbar = tk.Frame(root)
        self.toolbar.pack(fill=tk.X)

        self.create_toolbar()

    def create_toolbar(self):
        """Create toolbar buttons and controls."""
        tk.Button(self.toolbar, text="Open PDF", command=self.open_pdf).pack(side=tk.LEFT, padx=5)
        tk.Button(self.toolbar, text="Save PDF", command=self.save_pdf).pack(side=tk.LEFT, padx=5)

        # Annotation Tools
        self.tool_buttons = {}
        tools = [
            ("✔ Tick", "tick"), ("✖ Cross", "cross"), ("🖊 Text Box", "text"),
            ("✏ Pen Tool", "pen"), ("🧹 Erase", "erase")
        ]
        for text, tool in tools:
            button = tk.Button(self.toolbar, text=text, command=self.make_select_tool_function(tool))
            button.pack(side=tk.LEFT, padx=5)
            self.tool_buttons[tool] = button

        # Color Selector
        tk.Label(self.toolbar, text="Color:").pack(side=tk.LEFT, padx=5)
        self.color_dropdown = ttk.Combobox(self.toolbar, values=["Black", "Red", "Blue", "Green"], state="readonly")
        self.color_dropdown.pack(side=tk.LEFT, padx=5)
        self.color_dropdown.current(0)
        self.color_dropdown.bind("<<ComboboxSelected>>", self.change_color)

        # Zoom Controls
        tk.Button(self.toolbar, text="🔍 Zoom In", command=self.zoom_in).pack(side=tk.LEFT, padx=5)
        tk.Button(self.toolbar, text="🔍 Zoom Out", command=self.zoom_out).pack(side=tk.LEFT, padx=5)

    def make_select_tool_function(self, tool):
        def select_tool_function():
            self.select_tool(tool, self.tool_buttons[tool])
        return select_tool_function

    def open_pdf(self):
        """Open and load the PDF file."""
        self.pdf_path = filedialog.askopenfilename(filetypes=[("PDF Files", "*.pdf")])
        if self.pdf_path:
            try:
                self.doc = fitz.open(self.pdf_path)
                if self.doc.page_count == 0:
                    raise ValueError("The PDF file is empty.")
                self.show_pages()
            except Exception as e:
                messagebox.showerror("Error", f"Failed to open PDF file: {e}")

    def show_pages(self):
        """Render the visible pages of the PDF on the canvas."""
        if self.pdf_path and self.doc:
            try:
                self.canvas.delete("all")

                y_offset = 0
                self.page_images = []  # Store references to avoid garbage collection
                for page_num in range(len(self.doc)):
                    page = self.doc.load_page(page_num)
                    pix = page.get_pixmap(matrix=fitz.Matrix(self.zoom_factor, self.zoom_factor))
                    img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
                    img_tk = ImageTk.PhotoImage(img)

                    self.canvas.create_image(0, y_offset, anchor="nw", image=img_tk)
                    self.page_images.append(img_tk)  # Keep a reference to avoid garbage collection
                    y_offset += img.height

                # Update scroll region after displaying the pages
                self.canvas.config(scrollregion=(0, 0, img.width, y_offset))

                # Redraw annotations
                self.redraw_annotations()
            except Exception as e:
                messagebox.showerror("Error", f"Failed to render PDF pages: {e}")

    def redraw_annotations(self):
        """Redraw annotations on the canvas."""
        for annotation in self.annotations:
            if annotation['text'] == "line":
                scaled_pos = [coord * self.zoom_factor for coord in annotation['pos']]
                self.canvas.create_line(*scaled_pos, fill=annotation['color'], width=2)
            else:
                x, y = annotation['pos']
                x *= self.zoom_factor
                y *= self.zoom_factor
                annotation_id = self.canvas.create_text(x, y, text=annotation['text'], font=annotation['font'], fill=annotation['color'])
                annotation['canvas_id'] = annotation_id

    def save_pdf(self):
        """Save the annotated PDF file."""
        if self.doc:
            save_path = filedialog.asksaveasfilename(defaultextension=".pdf", filetypes=[("PDF Files", "*.pdf")])
            if save_path:
                try:
                    # Apply annotations to the PDF
                    for annotation in self.annotations:
                        page = self.doc[annotation['page']]
                        if annotation['text'] == "line":
                            x1, y1, x2, y2 = annotation['pos']
                            page.draw_line((x1, y1), (x2, y2), color=self.get_normalized_color(annotation['color']), width=2)
                        else:
                            page.insert_text((annotation['pos'][0], annotation['pos'][1]), 
                                             annotation['text'], 
                                             fontname="helv", 
                                             fontsize=12, 
                                             color=self.get_normalized_color(annotation['color']))

                    self.doc.save(save_path)
                    messagebox.showinfo("Success", "PDF saved successfully!")
                except Exception as e:
                    messagebox.showerror("Error", f"Failed to save PDF file: {e}")
        else:
            messagebox.showwarning("No Document", "No PDF is currently open.")

    def select_tool(self, tool, button):
        self.current_tool = tool
        self.canvas.config(cursor="circle" if tool == "erase" else "arrow")

        # Update button appearance
        for btn in self.tool_buttons.values():
            btn.config(relief=tk.RAISED)
        button.config(relief=tk.SUNKEN)

    def start_annotation(self, event):
        if self.current_tool == "erase":
            self.erase_annotation(event)
        else:
            self.add_annotation(event)

    def continue_annotation(self, event):
        if self.current_tool == "erase":
            self.erase_annotation(event)
        elif self.current_tool == "pen":
            self.draw_pen(event)

    def add_annotation(self, event):
        x, y = self.canvas.canvasx(event.x) / self.zoom_factor, self.canvas.canvasy(event.y) / self.zoom_factor
        current_page = self.get_current_page(y * self.zoom_factor)
        if self.current_tool in ["tick", "cross"]:
            text = "✔" if self.current_tool == "tick" else "✖"
            self.annotations.append({'pos': (x, y), 'text': text, 'font': ("Arial", int(20 * self.zoom_factor)), 'color': self.get_hex_color(), 'page': current_page})
            self.redraw_annotations()
        elif self.current_tool == "text":
            for annotation in self.annotations:
                if annotation['page'] == current_page and abs(annotation['pos'][0] - x) < 15 / self.zoom_factor and abs(annotation['pos'][1] - y) < 15 / self.zoom_factor:
                    text = simpledialog.askstring("Edit Text", "Edit text:", initialvalue=annotation['text'])
                    if text is not None:
                        annotation['text'] = text
                        self.canvas.delete(annotation['canvas_id'])
                        self.redraw_annotations()
                    return
            text = simpledialog.askstring("Input Text", "Enter text:")
            if text:
                self.annotations.append({'pos': (x, y), 'text': text, 'font': ("Arial", int(15 * self.zoom_factor)), 'color': self.get_hex_color(), 'page': current_page})
                self.redraw_annotations()

    def erase_annotation(self, event):
        x, y = self.canvas.canvasx(event.x) / self.zoom_factor, self.canvas.canvasy(event.y) / self.zoom_factor
        current_page = self.get_current_page(y * self.zoom_factor)
        to_remove = []
        for annotation in self.annotations:
            if annotation['page'] == current_page:
                if annotation['text'] == "line":
                    x1, y1, x2, y2 = annotation['pos']
                    if self.is_point_near_line(x, y, x1, y1, x2, y2, threshold=5 / self.zoom_factor):
                        to_remove.append(annotation)
                else:
                    ax, ay = annotation['pos']
                    # Check if the distance between the annotation and the cursor is small
                    if abs(ax - x) < 15 / self.zoom_factor and abs(ay - y) < 15 / self.zoom_factor:
                        to_remove.append(annotation)
        for annotation in to_remove:
            self.annotations.remove(annotation)
        self.show_pages()  # Refresh the canvas to show changes

    def is_point_near_line(self, px, py, x1, y1, x2, y2, threshold):
        """Check if a point (px, py) is near a line segment (x1, y1) to (x2, y2) within a given threshold."""
        dx = x2 - x1
        dy = y2 - y1
        if dx == 0 and dy == 0:
            # The line segment is a point
            return abs(px - x1) < threshold and abs(py - y1) < threshold
        t = ((px - x1) * dx + (py - y1) * dy) / (dx * dx + dy * dy)
        if t < 0:
            nearest_x, nearest_y = x1, y1
        elif t > 1:
            nearest_x, nearest_y = x2, y2
        else:
            nearest_x, nearest_y = x1 + t * dx, y1 + t * dy
        distance = ((px - nearest_x) ** 2 + (py - nearest_y) ** 2) ** 0.5
        return distance < threshold

    def get_current_page(self, y):
        """Get the current page number based on the y-coordinate."""
        y_offset = 0
        for page_num in range(len(self.doc)):
            page = self.doc.load_page(page_num)
            pix = page.get_pixmap(matrix=fitz.Matrix(self.zoom_factor, self.zoom_factor))
            if y_offset <= y < y_offset + pix.height:
                return page_num
            y_offset += pix.height
        return 0

    def draw_pen(self, event):
        x, y = self.canvas.canvasx(event.x) / self.zoom_factor, self.canvas.canvasy(event.y) / self.zoom_factor
        current_page = self.get_current_page(y * self.zoom_factor)
        if self.last_x and self.last_y:
            self.annotations.append({'pos': (self.last_x, self.last_y, x, y), 'text': "line", 'font': None, 'color': self.get_hex_color(), 'page': current_page})
            self.redraw_annotations()
        self.last_x, self.last_y = x, y

    def stop_drawing(self, event):
        self.last_x, self.last_y = None, None

    def change_color(self, event=None):
        colors = {"Black": (0, 0, 0), "Red": (1, 0, 0), "Blue": (0, 0, 1), "Green": (0, 1, 0)}
        self.text_color = colors[self.color_dropdown.get()]

    def get_hex_color(self):
        r, g, b = [int(c * 255) for c in self.text_color]
        return f'#{r:02x}{g:02x}{b:02x}'

    def get_normalized_color(self, hex_color):
        """Convert hex color to normalized float tuple."""
        hex_color = hex_color.lstrip('#')
        lv = len(hex_color)
        return tuple(int(hex_color[i:i+lv//3], 16) / 255.0 for i in range(0, lv, lv//3))

    def zoom_in(self):
        if self.zoom_factor < 3.0:
            self.zoom_factor += 0.2
            self.show_pages()

    def zoom_out(self):
        if self.zoom_factor > 0.5:
            self.zoom_factor -= 0.2
            self.show_pages()

    def scroll_canvas(self, event):
        """Scroll through the pages smoothly."""
        self.canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")


if __name__ == "__main__":
    root = tk.Tk()
    app = PDFAnnotator(root)
    root.mainloop()