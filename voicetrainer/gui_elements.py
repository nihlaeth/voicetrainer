"""More pythonic interface to common gui elements."""
from typing import List, Optional, Callable, Union, Tuple, Dict, Any
import tkinter as tk
from tkinter import ttk

class Widget:

    """Base class for widgets."""

    _widget = None
    _variable = None
    _text = None
    data_type = int

    def grid(self: Widget, *args, **kwargs):
        """Add widget to grid."""
        self._widget.grid(*args, **kwargs)

    def rowconfigure(self: Widget, *args, **kwargs):
        """Configure row."""
        self._widget.rowconfigure(*args, **kwargs)

    def columnconfigure(self: Widget, *args, **kwargs):
        """Configure column."""
        self._widget.columnconfigure(*args, **kwargs)

class IntMixin:

    """Methods for widgets using an integer value."""

    def set(self: Widget, value: int):
        """Set widget value."""
        self._widget.set(int(value))

    def get(self: Widget) -> int:
        """Return widget value."""
        return int(self._widget.get())

class ControlVarMixin:

    """Methods for widgets using either a StringVar or an IntVar."""

    def set(self: Widget, value: Union[str, int, bool]):
        """Set widget value."""
        if isinstance(self._variable, tk.StringVar):
            self._variable.set(str(value))
        elif isinstance(self._variable, tk.IntVar):
            self._variable.set(int(value))
        else:
            raise TypeError(
                'self._variable should be of type tk.IntVar or tk.StringVar')

    def get(self: Widget) -> Union[str, int, bool]:
        """Return widget value."""
        return self.data_type(self._variable.get())


class TextMixin:

    """Control text displayed on labels and buttons."""

    def set_text(self: tk.Widget, text: str):
        """Set text variable."""
        self._text.set(str(text))

    def get_text(self: tk.Widget) -> str:
        """Get text variable."""
        return str(self._text.get())

class TkMixin:

    """Methods specific to tk widgets."""

    def disable(self: Widget):
        """Disable widget using configure."""
        self._widget.configure(state=tk.DISABLED)

class TtkMixin:

    """Methods specific to ttk widgets."""

    def disable(self: Widget):
        """Disable widget using state."""
        self._widget.state(('disabled',))

class Scale(Widget, IntMixin, TkMixin):

    """Scale widget."""

    def __init__(
            self,
            parent: tk.Widget,
            length: int,
            from_: int,
            to: int,
            tickinterval: int=10,
            resolution: int=1,
            showvalue=False,
            orient: str=tk.VERTICAL,
            default: int=1,
            label: Optional[str]=None,
            command: Optional[Callable[[tk.Event], None]]=None):
        self._widget = tk.Scale(
            parent,
            from_=from_,
            to=to,
            tickinterval=tickinterval,
            resolution=resolution,
            length=length,
            showvalue=showvalue,
            orient=orient,
            label=label,
            command=command)
        self.set(default)

class OptionMenu(Widget, ControlVarMixin, TkMixin):

    """OptionMenu widget."""

    def __init__(
            self: Widget,
            parent: tk.Widget,
            option_list: List[str],
            default: str,
            command: Optional[Callable[[tk.Event], None]]=None):
        self.data_type = str
        self._variable = tk.StringVar()
        self._widget = tk.OptionMenu(
            parent,
            self._variable,
            *option_list,
            command=command)
        self.set(default)

class SpinBox(Widget, ControlVarMixin, TkMixin):

    """SpinBox widget."""

    def __init__(
            self: Widget,
            parent: tk.Widget,
            width: int,
            from_: int,
            to: int,
            increment: int=1,
            default: Union[int, str]=1,
            values: Optional[Tuple[str]]=None,
            wrap: bool=False,
            command: Optional[Callable[[tk.Event], None]]=None):
        self._variable = tk.StringVar()
        if values is None:
            self.data_type = int
            self._widget = tk.Spinbox(
                parent,
                width=width,
                from_=from_,
                to=to,
                increment=increment,
                textvariable=self.data_type,
                wrap=wrap,
                command=command)
        else:
            self.data_type = str
            self._widget = tk.Spinbox(
                parent,
                width=width,
                values=values,
                textvariable=self.data_type,
                wrap=wrap,
                command=command)
        self.set(default)

class Listbox(Widget, TkMixin):

    """Listbox widget."""

    def __init__(
            self: Widget,
            parent: tk.Widget,
            width: int,
            values: Tuple[str],
            selectmode: str=tk.MULTIPLE):
        self._frame = ttk.Frame(parent)
        self._frame.rowconfigure(0, weight=1)
        self._frame.columnconfigure(0, weight=1)
        self._scrollbar = tk.Scrollbar(self._frame, orient=tk.VERTICAL)
        self._scrollbar.grid(row=0, column=1, sticky=tk.NSEW)
        self._widget = tk.Listbox(
            self._frame,
            yscrollcommand=self._scrollbar.set,
            width=width,
            exportselection=False,
            selectmode=selectmode)
        self._scrollbar['command'] = self._widget.yview
        self._widget.grid(row=0, column=1, sticky=tk.NSEW)
        self._values = values
        self._update_values()
        self._frame.bind("<Button-4>", self._on_mouse_wheel)
        self._frame.bind("<Button-5>", self._on_mouse_wheel)

    def _on_mouse_wheel(self, event: tk.Event):
        self._widget.yview_scroll(-1 if event.num == 5 else 1, tk.UNITS)

    def __len__(self):
        return len(self._values)

    def __getitem__(
            self, key: Union[int, slice]) -> Union[str, List[str]]:
        return self._values[key]

    def __setitem__(
            self, key: Union[int, slice], value: Union[str, List[str]]):
        self._values[key] = value
        self._update_values()

    def __iter__(self):
        return iter(self._values)

    def __reversed__(self):
        return reversed(self._values)

    def __contains__(self, item: str) -> bool:
        return item in self._values

    def __add__(self, other):
        if isinstance(other, list):
            self._values += other
            self._update_values()
        else:
            raise NotImplementedError('{} is not of type list'.format(other))

    def __radd__(self, other):
        return other + self._values

    def __iadd__(self, other):
        self.__add__(other)

    def __mul__(self, other):
        if isinstance(other, int):
            self._values *= other
            self._update_values()
        else:
            raise NotImplementedError('{} is not of type int'.format(other))

    def __rmul__(self, other):
        self.__mul__(other)

    def __imul__(self, other):
        self.__mul__(other)

    def append(self, value):
        """Append value."""
        self._values.append(value)
        self._update_values()

    def count(self, item):
        """Count occurences of item."""
        return self._values.count(item)

    def index(self, item):
        """Return index of first occurence of item."""
        return self._values.index(item)

    def extend(self, extension):
        """Extend list."""
        self._values.extend(extension)
        self._update_values()

    def insert(self, index, value):
        """Insert item at index."""
        self._values.insert(index, value)
        self._update_values()

    def pop(self, index):
        """Pop value at index."""
        value = self._values.pop(index)
        self._update_values()
        return value

    def remove(self, item):
        """Remove first occurence of item."""
        self._values.remove(item)
        self._update_values()

    def reverse(self):
        """Reverse in place."""
        self._values.reverce()
        self._update_values()

    def sort(self, key: Optional[Callable[[str], Any]]=None, reverse=None):
        """Sort in place using key(item) to compare."""
        self._values.sort(key, reverse)
        self._update_values()

    def _update_values(self):
        selection = self.get()
        if self._widget.size() > 0:
            self._widget.delete(0, tk.END)
        self._widget.insert(0, *self._values)
        self.set(selection)

    def get(self: Widget) -> List[str]:
        """Get list of selected items."""
        selected = []
        for index in self._widget.curselection():
            selected.append(self._values[index])
        return selected

    def set(self: Widget, values: Dict[bool]):
        """Set every key in values to selected or unselected."""
        for key in values:
            if key not in self._values:
                continue
            index = self._values.index(key)
            if values[key]:
                self._widget.selection_set(index)
            else:
                self._widget.selection_clear(index)

class Checkbutton(Widget, ControlVarMixin, TextMixin, TtkMixin):

    """Checkbutton widget."""

    def __init__(
            self: Widget,
            parent: tk.Widget,
            text: str,
            default: bool=False,
            command: Optional[Callable[[tk.Event], None]]=None):
        self.data_type = bool
        self._variable = tk.IntVar()
        self._text = tk.StringVar()
        self._widget = ttk.Checkbutton(
            parent,
            textvariable=self._text,
            variable=self._variable,
            command=command)
        self.set(default)
        self.set_text(text)

class Button(Widget, TextMixin, TtkMixin):

    """Button widget."""

    def __init__(
            self: Widget,
            parent: tk.Widget,
            text: str,
            command: Optional[Callable[[], None]]=None):
        self._text = tk.StringVar()
        self._widget = ttk.Button(
            parent,
            textvariable=self._text,
            command=command)
        self.set_text(text)

class Label(Widget, TextMixin, TtkMixin):

    """Label widget."""

    def __init__(
            self: Widget,
            parent: tk.Widget,
            text: str):
        self._text = tk.StringVar()
        self._widget = ttk.Label(
            parent,
            textvariable=self._text)
        self.set_text(text)
