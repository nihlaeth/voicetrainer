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

    @property
    def raw(self) -> tk.Widget:
        """Tkinter does not accept our awesone widgets, a tk.Widget is called for."""
        return self._widget

    def grid(self, *args, **kwargs):
        """Add widget to grid."""
        self._widget.grid(*args, **kwargs)

    def rowconfigure(self, *args, **kwargs):
        """Configure row."""
        self._widget.rowconfigure(*args, **kwargs)

    def columnconfigure(self, *args, **kwargs):
        """Configure column."""
        self._widget.columnconfigure(*args, **kwargs)

    def winfo_toplevel(self):
        """Retrieve toplevel instance."""
        return self._widget.winfo_toplevel()

    def bind(self, event, callback):
        """Bind event to callback."""
        self._widget.bind(event, callback)

class IntMixin:

    """Methods for widgets using an integer value."""

    def set(self, value: int):
        """Set widget value."""
        self._widget.set(int(value))

    def get(self) -> int:
        """Return widget value."""
        return int(self._widget.get())

class ControlVarMixin:

    """Methods for widgets using either a StringVar or an IntVar."""

    def set(self, value: Union[str, int, bool]):
        """Set widget value."""
        if isinstance(self._variable, tk.StringVar):
            self._variable.set(str(value))
        elif isinstance(self._variable, tk.IntVar):
            self._variable.set(int(value))
        else:
            raise TypeError(
                'self._variable should be of type tk.IntVar or tk.StringVar')

    def get(self) -> Union[str, int, bool]:
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

    def disable(self):
        """Disable widget using configure."""
        self._widget.configure(state=tk.DISABLED)

class TtkMixin:

    """Methods specific to ttk widgets."""

    def disable(self):
        """Disable widget using state."""
        self._widget.state(('disabled',))

class SequenceMixin:

    """Methods for sequence types."""

    _values = None

    def __len__(self):
        return len(self._values)

    def __getitem__(self, key: Union[int, slice]) -> Any:
        return self._values[key]

    def __setitem__(self, key: Union[int, slice], value: Any):
        self._values[key] = value
        self._update_values()

    def __iter__(self):
        return iter(self._values)

    def __reversed__(self):
        return reversed(self._values)

    def __contains__(self, item: Any) -> bool:
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

class Scale(Widget, IntMixin, TkMixin):

    """Scale widget."""

    def __init__(
            self,
            parent: Union[Widget, tk.Widget],
            length: int,
            from_: int,
            to: int,
            tickinterval: int=10,
            resolution: int=1,
            showvalue: bool=False,
            orient: str=tk.VERTICAL,
            default: int=1,
            label: Optional[str]=None,
            command: Optional[Callable[[tk.Event], None]]=None):
        if isinstance(parent, Widget):
            parent = parent.raw
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
            self,
            parent: Union[Widget, tk.Widget],
            option_list: List[str],
            default: str,
            command: Optional[Callable[[tk.Event], None]]=None):
        if isinstance(parent, Widget):
            parent = parent.raw
        self.data_type = str
        self._variable = tk.StringVar()
        self._widget = tk.OptionMenu(
            parent,
            self._variable,
            *option_list,
            command=command)
        self.set(default)

class Spinbox(Widget, ControlVarMixin, TkMixin):

    """SpinBox widget."""

    def __init__(
            self,
            parent: Union[Widget, tk.Widget],
            width: int,
            from_: int,
            to: int,
            increment: int=1,
            default: Union[int, str]=1,
            values: Optional[Tuple[str]]=None,
            wrap: bool=False,
            command: Optional[Callable[[tk.Event], None]]=None):
        if isinstance(parent, Widget):
            parent = parent.raw
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

class Listbox(Widget, SequenceMixin, TkMixin):

    """Listbox widget."""

    def __init__(
            self,
            parent: Union[Widget, tk.Widget],
            width: int,
            values: Tuple[str],
            selectmode: str=tk.MULTIPLE):
        if isinstance(parent, Widget):
            parent = parent.raw
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

    def _update_values(self):
        selection = self.get()
        if self._widget.size() > 0:
            self._widget.delete(0, tk.END)
        self._widget.insert(0, *self._values)
        self.set(selection)

    def get(self) -> List[str]:
        """Get list of selected items."""
        selected = []
        for index in self._widget.curselection():
            selected.append(self._values[index])
        return selected

    def set(self, values: Dict[str, bool]):
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
            self,
            parent: Union[Widget, tk.Widget],
            text: str,
            default: bool=False,
            command: Optional[Callable[[tk.Event], None]]=None):
        if isinstance(parent, Widget):
            parent = parent.raw
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
            self,
            parent: Union[Widget, tk.Widget],
            text: str,
            command: Optional[Callable[[], None]]=None):
        if isinstance(parent, Widget):
            parent = parent.raw
        self._text = tk.StringVar()
        self._widget = ttk.Button(
            parent,
            textvariable=self._text,
            command=command)
        self.set_text(text)

class Label(Widget, TextMixin, TtkMixin):

    """Label widget."""

    def __init__(
            self,
            parent: Union[Widget, tk.Widget],
            text: str):
        if isinstance(parent, Widget):
            parent = parent.raw
        self._text = tk.StringVar()
        self._widget = ttk.Label(
            parent,
            textvariable=self._text)
        self.set_text(text)

    def set(self, value: str):
        self.set_text(value)

class Frame(Widget, TtkMixin):

    """Frame widget."""

    def __init__(
            self,
            parent: Union[Widget, tk.Widget]):
        if isinstance(parent, Widget):
            parent = parent.raw
        self._widget = ttk.Frame(parent)

class LabelFrame(Widget, TextMixin, TtkMixin):

    """Label widget."""

    def __init__(
            self,
            parent: Union[Widget, tk.Widget],
            text: str):
        if isinstance(parent, Widget):
            parent = parent.raw
        self._text = Label(parent, text=text)
        self._widget = ttk.LabelFrame(
            parent,
            labelwidget=self._text.raw)
        self.set_text(text)


class Notebook(Widget, SequenceMixin, TtkMixin):

    """
    Notebook widget.

    Is sequence. Tab data in the form of:
        {'name': str, 'widget': Union[tk.Widget, Widged]}
    """

    def __init__(
            self,
            parent: Union[Widget, tk.Widget]):
        if isinstance(parent, Widget):
            parent = parent.raw
        self._widget = ttk.Notebook(parent)
        self._values = []

    def _get_tabs(self) -> List[str]:
        return [
            self._widget.tab(tab_id)['text'] for tab_id in self._widget.tabs()]

    def _update_values(self):
        """Sync list in self._values with notebook tabs."""
        for i, tab_data in enumerate(self._values):
            tabs = self._get_tabs()
            if len(tabs) <= i or tab_data['name'] != tabs[i]:
                if isinstance(tab_data['widget'], Widget):
                    widget = tab_data['widget'].raw
                else:
                    widget = tab_data['widget']
                where = "end" if len(tabs) <= i + 1 else tabs[i + 1]
                self._widget.insert(
                    where, widget, text=tab_data['name'])
        if len(self._values) == len(self._widget.tabs()):
            return
        # now delete all tabs not in self._values
        # we can just cut off the end, since we just made sure
        # the first part matches self._values
        for index in range(len(self._values), len(self._widget.tabs())):
            self._widget.forget(index)

    def get(self) -> Tuple[int, str]:
        """Return index and name on active tab."""
        tab_id = self._widget.select()
        return (
            self._widget.index(tab_id), self._widget.tab(tab_id)['text'])

    def set(self, value: str):
        """Set active tab."""
        index = self._get_tabs().index(value)
        self._widget.select(index)
