from __future__ import annotations

import contextlib
import math
from datetime import date, datetime, time, timedelta
from decimal import Decimal as PyDecimal
from typing import (
    TYPE_CHECKING,
    Any,
    Callable,
    ClassVar,
    Collection,
    Generator,
    Iterable,
    Literal,
    Mapping,
    NoReturn,
    Sequence,
    Union,
    overload,
)

import polars._reexport as pl
from polars import functions as F
from polars._utils.construction import (
    arrow_to_pyseries,
    dataframe_to_pyseries,
    iterable_to_pyseries,
    numpy_to_idxs,
    numpy_to_pyseries,
    pandas_to_pyseries,
    sequence_to_pyseries,
    series_to_pyseries,
)
from polars._utils.convert import (
    date_to_int,
    datetime_to_int,
    time_to_int,
    timedelta_to_int,
)
from polars._utils.deprecation import (
    deprecate_function,
    deprecate_nonkeyword_arguments,
    deprecate_renamed_function,
    deprecate_renamed_parameter,
    issue_deprecation_warning,
)
from polars._utils.unstable import unstable
from polars._utils.various import (
    BUILDING_SPHINX_DOCS,
    _is_generator,
    no_default,
    parse_version,
    range_to_slice,
    scale_bytes,
    sphinx_accessor,
    warn_null_comparison,
)
from polars._utils.wrap import wrap_df
from polars.datatypes import (
    Array,
    Boolean,
    Categorical,
    Date,
    Datetime,
    Decimal,
    Duration,
    Enum,
    Float64,
    Int8,
    Int16,
    Int32,
    Int64,
    List,
    Null,
    Object,
    String,
    Time,
    UInt8,
    UInt16,
    UInt32,
    UInt64,
    Unknown,
    dtype_to_ctype,
    is_polars_dtype,
    maybe_cast,
    numpy_char_code_to_dtype,
    py_type_to_dtype,
    supported_numpy_char_code,
)
from polars.dependencies import (
    _HVPLOT_AVAILABLE,
    _PYARROW_AVAILABLE,
    _check_for_numpy,
    _check_for_pandas,
    _check_for_pyarrow,
    hvplot,
    import_optional,
)
from polars.dependencies import numpy as np
from polars.dependencies import pandas as pd
from polars.dependencies import pyarrow as pa
from polars.exceptions import ModuleUpgradeRequired, ShapeError
from polars.meta import get_index_type
from polars.series.array import ArrayNameSpace
from polars.series.binary import BinaryNameSpace
from polars.series.categorical import CatNameSpace
from polars.series.datetime import DateTimeNameSpace
from polars.series.list import ListNameSpace
from polars.series.string import StringNameSpace
from polars.series.struct import StructNameSpace
from polars.series.utils import expr_dispatch, get_ffi_func
from polars.slice import PolarsSlice

with contextlib.suppress(ImportError):  # Module not available when building docs
    from polars.polars import PyDataFrame, PySeries

if TYPE_CHECKING:
    import sys

    import torch
    from hvplot.plotting.core import hvPlotTabularPolars

    from polars import DataFrame, DataType, Expr
    from polars._utils.various import (
        NoDefault,
    )
    from polars.series._numpy import SeriesView
    from polars.type_aliases import (
        BufferInfo,
        ClosedInterval,
        ComparisonOperator,
        FillNullStrategy,
        InterpolationMethod,
        IntoExpr,
        IntoExprColumn,
        NonNestedLiteral,
        NullBehavior,
        NumericLiteral,
        OneOrMoreDataTypes,
        PolarsDataType,
        PythonLiteral,
        RankMethod,
        RollingInterpolationMethod,
        SearchSortedSide,
        SeriesBuffers,
        SizeUnit,
        TemporalLiteral,
    )

    if sys.version_info >= (3, 11):
        from typing import Self
    else:
        from typing_extensions import Self
elif BUILDING_SPHINX_DOCS:
    property = sphinx_accessor

ArrayLike = Union[
    Sequence[Any],
    "Series",
    "pa.Array",
    "pa.ChunkedArray",
    "np.ndarray[Any, Any]",
    "pd.Series[Any]",
    "pd.DatetimeIndex",
]


@expr_dispatch
class Series:
    """
    A Series represents a single column in a polars DataFrame.

    Parameters
    ----------
    name : str, default None
        Name of the Series. Will be used as a column name when used in a DataFrame.
        When not specified, name is set to an empty string.
    values : ArrayLike, default None
        One-dimensional data in various forms. Supported are: Sequence, Series,
        pyarrow Array, and numpy ndarray.
    dtype : DataType, default None
        Data type of the resulting Series. If set to `None` (default), the data type is
        inferred from the `values` input. The strategy for data type inference depends
        on the `strict` parameter:

        - If `strict` is set to True (default), the inferred data type is equal to the
          first non-null value, or `Null` if all values are null.
        - If `strict` is set to False, the inferred data type is the supertype of the
          values, or :class:`Object` if no supertype can be found. **WARNING**: A full
          pass over the values is required to determine the supertype.
        - If no values were passed, the resulting data type is :class:`Null`.

    strict : bool, default True
        Throw an error if any value does not exactly match the given or inferred data
        type. If set to `False`, values that do not match the data type are cast to
        that data type or, if casting is not possible, set to null instead.
    nan_to_null : bool, default False
        In case a numpy array is used to create this Series, indicate how to deal
        with np.nan values. (This parameter is a no-op on non-numpy data).
    dtype_if_empty : DataType, default Null
        Data type of the Series if `values` contains no non-null data.

        .. deprecated:: 0.20.6
            The data type for empty Series will always be `Null`, unless `dtype` is
            specified. To preserve behavior, check if the resulting Series has data type
            `Null` and cast to the desired data type.
            This parameter will be removed in the next breaking release.

    Examples
    --------
    Constructing a Series by specifying name and values positionally:

    >>> s = pl.Series("a", [1, 2, 3])
    >>> s
    shape: (3,)
    Series: 'a' [i64]
    [
            1
            2
            3
    ]

    Notice that the dtype is automatically inferred as a polars Int64:

    >>> s.dtype
    Int64

    Constructing a Series with a specific dtype:

    >>> s2 = pl.Series("a", [1, 2, 3], dtype=pl.Float32)
    >>> s2
    shape: (3,)
    Series: 'a' [f32]
    [
        1.0
        2.0
        3.0
    ]

    It is possible to construct a Series with values as the first positional argument.
    This syntax considered an anti-pattern, but it can be useful in certain
    scenarios. You must specify any other arguments through keywords.

    >>> s3 = pl.Series([1, 2, 3])
    >>> s3
    shape: (3,)
    Series: '' [i64]
    [
            1
            2
            3
    ]
    """

    _s: PySeries = None
    _accessors: ClassVar[set[str]] = {
        "arr",
        "cat",
        "dt",
        "list",
        "str",
        "bin",
        "struct",
        "plot",
    }

    def __init__(
        self,
        name: str | ArrayLike | None = None,
        values: ArrayLike | None = None,
        dtype: PolarsDataType | None = None,
        *,
        strict: bool = True,
        nan_to_null: bool = False,
        dtype_if_empty: PolarsDataType = Null,
    ):
        if dtype_if_empty != Null:
            issue_deprecation_warning(
                "The `dtype_if_empty` parameter for the Series constructor is deprecated."
                " The data type for empty Series will always be Null, unless `dtype` is specified."
                " To preserve behavior, check if the resulting Series has data type Null and cast to the desired data type."
                " This parameter will be removed in the next breaking release.",
                version="0.20.6",
            )

        # If 'Unknown' treat as None to trigger type inference
        if dtype == Unknown:
            dtype = None
        elif dtype is not None and not is_polars_dtype(dtype):
            # Raise early error on invalid dtype
            if not is_polars_dtype(
                pl_dtype := py_type_to_dtype(dtype, raise_unmatched=False)
            ):
                msg = f"given dtype: {dtype!r} is not a valid Polars data type and cannot be converted into one"
                raise ValueError(msg)
            else:
                dtype = pl_dtype

        # Handle case where values are passed as the first argument
        original_name: str | None = None
        if name is None:
            name = ""
        elif isinstance(name, str):
            original_name = name
        else:
            if values is None:
                values = name
                name = ""
            else:
                msg = "Series name must be a string"
                raise TypeError(msg)

        if isinstance(values, Sequence):
            self._s = sequence_to_pyseries(
                name,
                values,
                dtype=dtype,
                strict=strict,
                nan_to_null=nan_to_null,
            )

        elif values is None:
            self._s = sequence_to_pyseries(name, [], dtype=dtype)

        elif _check_for_numpy(values) and isinstance(values, np.ndarray):
            self._s = numpy_to_pyseries(
                name, values, strict=strict, nan_to_null=nan_to_null
            )
            if values.dtype.type in [np.datetime64, np.timedelta64]:
                # cast to appropriate dtype, handling NaT values
                input_dtype = _resolve_temporal_dtype(None, values.dtype)
                dtype = _resolve_temporal_dtype(dtype, values.dtype)
                if dtype is not None:
                    self._s = (
                        # `values.dtype` has already been validated in
                        # `numpy_to_pyseries`, so `input_dtype` can't be `None`
                        self.cast(input_dtype)  # type: ignore[arg-type]
                        .cast(dtype)
                        .scatter(np.argwhere(np.isnat(values)).flatten(), None)
                        ._s
                    )
                    return

            if dtype is not None:
                self._s = self.cast(dtype, strict=strict)._s

        elif _check_for_pyarrow(values) and isinstance(
            values, (pa.Array, pa.ChunkedArray)
        ):
            self._s = arrow_to_pyseries(name, values, dtype=dtype, strict=strict)

        elif _check_for_pandas(values) and isinstance(
            values, (pd.Series, pd.Index, pd.DatetimeIndex)
        ):
            self._s = pandas_to_pyseries(name, values, dtype=dtype, strict=strict)

        elif _is_generator(values):
            self._s = iterable_to_pyseries(name, values, dtype=dtype, strict=strict)

        elif isinstance(values, Series):
            self._s = series_to_pyseries(
                original_name, values, dtype=dtype, strict=strict
            )

        elif isinstance(values, pl.DataFrame):
            self._s = dataframe_to_pyseries(
                original_name, values, dtype=dtype, strict=strict
            )

        else:
            msg = (
                f"Series constructor called with unsupported type {type(values).__name__!r}"
                " for the `values` parameter"
            )
            raise TypeError(msg)

        # Implementation of deprecated `dtype_if_empty` functionality
        if dtype_if_empty != Null and self.dtype == Null:
            self._s = self._s.cast(dtype_if_empty, False)

    @classmethod
    def _from_pyseries(cls, pyseries: PySeries) -> Self:
        series = cls.__new__(cls)
        series._s = pyseries
        return series

    @classmethod
    def _import_from_c(cls, name: str, pointers: list[tuple[int, int]]) -> Self:
        """
        Construct a Series from Arrows C interface.

        Warning
        -------
        This will read the `array` pointer without moving it. The host process should
        garbage collect the heap pointer, but not its contents.
        """
        return cls._from_pyseries(PySeries._import_from_c(name, pointers))

    def _get_buffer_info(self) -> BufferInfo:
        """
        Return pointer, offset, and length information about the underlying buffer.

        Returns
        -------
        tuple of ints
            Tuple of the form (pointer, offset, length)

        Raises
        ------
        TypeError
            If the `Series` data type is not physical.
        ComputeError
            If the `Series` contains multiple chunks.

        Notes
        -----
        This method is mainly intended for use with the dataframe interchange protocol.
        """
        return self._s._get_buffer_info()

    def _get_buffers(self) -> SeriesBuffers:
        """
        Return the underlying values, validity, and offsets buffers as Series.

        The values buffer always exists.
        The validity buffer may not exist if the column contains no null values.
        The offsets buffer only exists for Series of data type `String` and `List`.

        Returns
        -------
        dict
            Dictionary with `"values"`, `"validity"`, and `"offsets"` keys mapping
            to the corresponding buffer or `None` if the buffer doesn't exist.

        Warnings
        --------
        The underlying buffers for `String` Series cannot be represented in this
        format. Instead, the buffers are converted to a values and offsets buffer.

        Notes
        -----
        This method is mainly intended for use with the dataframe interchange protocol.
        """
        buffers = self._s._get_buffers()
        keys = ("values", "validity", "offsets")
        return {  # type: ignore[return-value]
            k: self._from_pyseries(b) if b is not None else b
            for k, b in zip(keys, buffers)
        }

    @classmethod
    def _from_buffer(
        self, dtype: PolarsDataType, buffer_info: BufferInfo, owner: Any
    ) -> Self:
        """
        Construct a Series from information about its underlying buffer.

        Parameters
        ----------
        dtype
            The data type of the buffer.
            Must be a physical type (integer, float, or boolean).
        buffer_info
            Tuple containing buffer information in the form `(pointer, offset, length)`.
        owner
            The object owning the buffer.

        Returns
        -------
        Series

        Raises
        ------
        TypeError
            When the given `dtype` is not supported.

        Notes
        -----
        This method is mainly intended for use with the dataframe interchange protocol.
        """
        return self._from_pyseries(PySeries._from_buffer(dtype, buffer_info, owner))

    @classmethod
    def _from_buffers(
        self,
        dtype: PolarsDataType,
        data: Series | Sequence[Series],
        validity: Series | None = None,
    ) -> Self:
        """
        Construct a Series from information about its underlying buffers.

        Parameters
        ----------
        dtype
            The data type of the resulting Series.
        data
            Buffers describing the data. For most data types, this is a single Series of
            the physical data type of `dtype`. Some data types require multiple buffers:

            - `String`: A data buffer of type `UInt8` and an offsets buffer
              of type `Int64`. Note that this does not match how the data
              is represented internally and data copy is required to construct
              the Series.
        validity
            Validity buffer. If specified, must be a Series of data type `Boolean`.

        Returns
        -------
        Series

        Raises
        ------
        TypeError
            When the given `dtype` is not supported or the other inputs do not match
            the requirements for constructing a Series of the given `dtype`.

        Warnings
        --------
        Constructing a `String` Series requires specifying a values and offsets buffer,
        which does not match the actual underlying buffers. The values and offsets
        buffer are converted into the actual buffers, which copies data.

        Notes
        -----
        This method is mainly intended for use with the dataframe interchange protocol.
        """
        if isinstance(data, Series):
            data = [data._s]
        else:
            data = [s._s for s in data]
        if validity is not None:
            validity = validity._s
        return self._from_pyseries(PySeries._from_buffers(dtype, data, validity))

    @property
    def dtype(self) -> DataType:
        """
        Get the data type of this Series.

        Examples
        --------
        >>> s = pl.Series("a", [1, 2, 3])
        >>> s.dtype
        Int64
        """
        return self._s.dtype()

    @property
    def flags(self) -> dict[str, bool]:
        """
        Get flags that are set on the Series.

        Examples
        --------
        >>> s = pl.Series("a", [1, 2, 3])
        >>> s.flags
        {'SORTED_ASC': False, 'SORTED_DESC': False}
        """
        out = {
            "SORTED_ASC": self._s.is_sorted_ascending_flag(),
            "SORTED_DESC": self._s.is_sorted_descending_flag(),
        }
        if self.dtype == List:
            out["FAST_EXPLODE"] = self._s.can_fast_explode_flag()
        return out

    @property
    def inner_dtype(self) -> DataType | None:
        """
        Get the inner dtype in of a List typed Series.

        .. deprecated:: 0.19.14
            Use `Series.dtype.inner` instead.

        Returns
        -------
        DataType
        """
        issue_deprecation_warning(
            "`Series.inner_dtype` is deprecated. Use `Series.dtype.inner` instead.",
            version="0.19.14",
        )
        try:
            return self.dtype.inner  # type: ignore[attr-defined]
        except AttributeError:
            return None

    @property
    def name(self) -> str:
        """
        Get the name of this Series.

        Examples
        --------
        >>> s = pl.Series("a", [1, 2, 3])
        >>> s.name
        'a'
        """
        return self._s.name()

    @property
    def shape(self) -> tuple[int]:
        """
        Shape of this Series.

        Examples
        --------
        >>> s = pl.Series("a", [1, 2, 3])
        >>> s.shape
        (3,)
        """
        return (self._s.len(),)

    def __bool__(self) -> NoReturn:
        msg = (
            "the truth value of a Series is ambiguous"
            "\n\n"
            "Here are some things you might want to try:\n"
            "- instead of `if s`, use `if not s.is_empty()`\n"
            "- instead of `s1 and s2`, use `s1 & s2`\n"
            "- instead of `s1 or s2`, use `s1 | s2`\n"
            "- instead of `s in [y, z]`, use `s.is_in([y, z])`\n"
        )
        raise TypeError(msg)

    def __getstate__(self) -> bytes:
        return self._s.__getstate__()

    def __setstate__(self, state: bytes) -> None:
        self._s = Series()._s  # Initialize with a dummy
        self._s.__setstate__(state)

    def __str__(self) -> str:
        s_repr: str = self._s.as_str()
        return s_repr.replace("Series", f"{self.__class__.__name__}", 1)

    def __repr__(self) -> str:
        return self.__str__()

    def __len__(self) -> int:
        return self.len()

    def __and__(self, other: Series) -> Self:
        if not isinstance(other, Series):
            other = Series([other])
        return self._from_pyseries(self._s.bitand(other._s))

    def __rand__(self, other: Series) -> Series:
        if not isinstance(other, Series):
            other = Series([other])
        return other & self

    def __or__(self, other: Series) -> Self:
        if not isinstance(other, Series):
            other = Series([other])
        return self._from_pyseries(self._s.bitor(other._s))

    def __ror__(self, other: Series) -> Series:
        if not isinstance(other, Series):
            other = Series([other])
        return other | self

    def __xor__(self, other: Series) -> Self:
        if not isinstance(other, Series):
            other = Series([other])
        return self._from_pyseries(self._s.bitxor(other._s))

    def __rxor__(self, other: Series) -> Series:
        if not isinstance(other, Series):
            other = Series([other])
        return other ^ self

    def _comp(self, other: Any, op: ComparisonOperator) -> Series:
        # special edge-case; boolean broadcast series (eq/neq) is its own result
        if self.dtype == Boolean and isinstance(other, bool) and op in ("eq", "neq"):
            if (other is True and op == "eq") or (other is False and op == "neq"):
                return self.clone()
            elif (other is False and op == "eq") or (other is True and op == "neq"):
                return ~self

        elif isinstance(other, float) and self.dtype.is_integer():
            # require upcast when comparing int series to float value
            self = self.cast(Float64)
            f = get_ffi_func(op + "_<>", Float64, self._s)
            assert f is not None
            return self._from_pyseries(f(other))

        elif isinstance(other, datetime):
            if self.dtype == Date:
                # require upcast when comparing date series to datetime
                self = self.cast(Datetime("us"))
                time_unit = "us"
            elif self.dtype == Datetime:
                # Use local time zone info
                time_zone = self.dtype.time_zone  # type: ignore[attr-defined]
                if str(other.tzinfo) != str(time_zone):
                    msg = f"Datetime time zone {other.tzinfo!r} does not match Series timezone {time_zone!r}"
                    raise TypeError(msg)
                time_unit = self.dtype.time_unit  # type: ignore[attr-defined]
            else:
                msg = f"cannot compare datetime.datetime to Series of type {self.dtype}"
                raise ValueError(msg)
            ts = datetime_to_int(other, time_unit)  # type: ignore[arg-type]
            f = get_ffi_func(op + "_<>", Int64, self._s)
            assert f is not None
            return self._from_pyseries(f(ts))

        elif isinstance(other, time) and self.dtype == Time:
            d = time_to_int(other)
            f = get_ffi_func(op + "_<>", Int64, self._s)
            assert f is not None
            return self._from_pyseries(f(d))

        elif isinstance(other, timedelta) and self.dtype == Duration:
            time_unit = self.dtype.time_unit  # type: ignore[attr-defined]
            td = timedelta_to_int(other, time_unit)  # type: ignore[arg-type]
            f = get_ffi_func(op + "_<>", Int64, self._s)
            assert f is not None
            return self._from_pyseries(f(td))

        elif self.dtype in [Categorical, Enum] and not isinstance(other, Series):
            other = Series([other])

        elif isinstance(other, date) and self.dtype == Date:
            d = date_to_int(other)
            f = get_ffi_func(op + "_<>", Int32, self._s)
            assert f is not None
            return self._from_pyseries(f(d))

        if isinstance(other, Sequence) and not isinstance(other, str):
            if self.dtype in (List, Array):
                other = [other]
            other = Series("", other)
            if other.dtype == Null:
                other.cast(self.dtype)

        if isinstance(other, Series):
            return self._from_pyseries(getattr(self._s, op)(other._s))

        if other is not None:
            other = maybe_cast(other, self.dtype)
        f = get_ffi_func(op + "_<>", self.dtype, self._s)
        if f is None:
            return NotImplemented

        return self._from_pyseries(f(other))

    @overload  # type: ignore[override]
    def __eq__(self, other: Expr) -> Expr: ...  # type: ignore[overload-overlap]

    @overload
    def __eq__(self, other: Any) -> Series: ...

    def __eq__(self, other: Any) -> Series | Expr:
        warn_null_comparison(other)
        if isinstance(other, pl.Expr):
            return F.lit(self).__eq__(other)
        return self._comp(other, "eq")

    @overload  # type: ignore[override]
    def __ne__(self, other: Expr) -> Expr:  # type: ignore[overload-overlap]
        ...

    @overload
    def __ne__(self, other: Any) -> Series: ...

    def __ne__(self, other: Any) -> Series | Expr:
        warn_null_comparison(other)
        if isinstance(other, pl.Expr):
            return F.lit(self).__ne__(other)
        return self._comp(other, "neq")

    @overload
    def __gt__(self, other: Expr) -> Expr:  # type: ignore[overload-overlap]
        ...

    @overload
    def __gt__(self, other: Any) -> Series: ...

    def __gt__(self, other: Any) -> Series | Expr:
        warn_null_comparison(other)
        if isinstance(other, pl.Expr):
            return F.lit(self).__gt__(other)
        return self._comp(other, "gt")

    @overload
    def __lt__(self, other: Expr) -> Expr:  # type: ignore[overload-overlap]
        ...

    @overload
    def __lt__(self, other: Any) -> Series: ...

    def __lt__(self, other: Any) -> Series | Expr:
        warn_null_comparison(other)
        if isinstance(other, pl.Expr):
            return F.lit(self).__lt__(other)
        return self._comp(other, "lt")

    @overload
    def __ge__(self, other: Expr) -> Expr:  # type: ignore[overload-overlap]
        ...

    @overload
    def __ge__(self, other: Any) -> Series: ...

    def __ge__(self, other: Any) -> Series | Expr:
        warn_null_comparison(other)
        if isinstance(other, pl.Expr):
            return F.lit(self).__ge__(other)
        return self._comp(other, "gt_eq")

    @overload
    def __le__(self, other: Expr) -> Expr:  # type: ignore[overload-overlap]
        ...

    @overload
    def __le__(self, other: Any) -> Series: ...

    def __le__(self, other: Any) -> Series | Expr:
        warn_null_comparison(other)
        if isinstance(other, pl.Expr):
            return F.lit(self).__le__(other)
        return self._comp(other, "lt_eq")

    @overload
    def le(self, other: Expr) -> Expr:  # type: ignore[overload-overlap]
        ...

    @overload
    def le(self, other: Any) -> Series: ...

    def le(self, other: Any) -> Series | Expr:
        """Method equivalent of operator expression `series <= other`."""
        return self.__le__(other)

    @overload
    def lt(self, other: Expr) -> Expr:  # type: ignore[overload-overlap]
        ...

    @overload
    def lt(self, other: Any) -> Series: ...

    def lt(self, other: Any) -> Series | Expr:
        """Method equivalent of operator expression `series < other`."""
        return self.__lt__(other)

    @overload
    def eq(self, other: Expr) -> Expr:  # type: ignore[overload-overlap]
        ...

    @overload
    def eq(self, other: Any) -> Series: ...

    def eq(self, other: Any) -> Series | Expr:
        """Method equivalent of operator expression `series == other`."""
        return self.__eq__(other)

    @overload
    def eq_missing(self, other: Expr) -> Expr:  # type: ignore[overload-overlap]
        ...

    @overload
    def eq_missing(self, other: Any) -> Series: ...

    def eq_missing(self, other: Any) -> Series | Expr:
        """
        Method equivalent of equality operator `series == other` where `None == None`.

        This differs from the standard `ne` where null values are propagated.

        Parameters
        ----------
        other
            A literal or expression value to compare with.

        See Also
        --------
        ne_missing
        eq

        Examples
        --------
        >>> s1 = pl.Series("a", [333, 200, None])
        >>> s2 = pl.Series("a", [100, 200, None])
        >>> s1.eq(s2)
        shape: (3,)
        Series: 'a' [bool]
        [
            false
            true
            null
        ]
        >>> s1.eq_missing(s2)
        shape: (3,)
        Series: 'a' [bool]
        [
            false
            true
            true
        ]
        """
        if isinstance(other, pl.Expr):
            return F.lit(self).eq_missing(other)
        return self.to_frame().select(F.col(self.name).eq_missing(other)).to_series()

    @overload
    def ne(self, other: Expr) -> Expr:  # type: ignore[overload-overlap]
        ...

    @overload
    def ne(self, other: Any) -> Series: ...

    def ne(self, other: Any) -> Series | Expr:
        """Method equivalent of operator expression `series != other`."""
        return self.__ne__(other)

    @overload
    def ne_missing(self, other: Expr) -> Expr:  # type: ignore[overload-overlap]
        ...

    @overload
    def ne_missing(self, other: Any) -> Series: ...

    def ne_missing(self, other: Any) -> Series | Expr:
        """
        Method equivalent of equality operator `series != other` where `None == None`.

        This differs from the standard `ne` where null values are propagated.

        Parameters
        ----------
        other
            A literal or expression value to compare with.

        See Also
        --------
        eq_missing
        ne

        Examples
        --------
        >>> s1 = pl.Series("a", [333, 200, None])
        >>> s2 = pl.Series("a", [100, 200, None])
        >>> s1.ne(s2)
        shape: (3,)
        Series: 'a' [bool]
        [
            true
            false
            null
        ]
        >>> s1.ne_missing(s2)
        shape: (3,)
        Series: 'a' [bool]
        [
            true
            false
            false
        ]
        """
        if isinstance(other, pl.Expr):
            return F.lit(self).ne_missing(other)
        return self.to_frame().select(F.col(self.name).ne_missing(other)).to_series()

    @overload
    def ge(self, other: Expr) -> Expr:  # type: ignore[overload-overlap]
        ...

    @overload
    def ge(self, other: Any) -> Series: ...

    def ge(self, other: Any) -> Series | Expr:
        """Method equivalent of operator expression `series >= other`."""
        return self.__ge__(other)

    @overload
    def gt(self, other: Expr) -> Expr:  # type: ignore[overload-overlap]
        ...

    @overload
    def gt(self, other: Any) -> Series: ...

    def gt(self, other: Any) -> Series | Expr:
        """Method equivalent of operator expression `series > other`."""
        return self.__gt__(other)

    def _arithmetic(self, other: Any, op_s: str, op_ffi: str) -> Self:
        if isinstance(other, pl.Expr):
            # expand pl.lit, pl.datetime, pl.duration Exprs to compatible Series
            other = self.to_frame().select_seq(other).to_series()
        elif other is None:
            other = pl.Series("", [None])

        if isinstance(other, Series):
            return self._from_pyseries(getattr(self._s, op_s)(other._s))
        elif _check_for_numpy(other) and isinstance(other, np.ndarray):
            return self._from_pyseries(getattr(self._s, op_s)(Series(other)._s))
        elif (
            isinstance(other, (float, date, datetime, timedelta, str))
            and not self.dtype.is_float()
        ):
            _s = sequence_to_pyseries(self.name, [other])
            if "rhs" in op_ffi:
                return self._from_pyseries(getattr(_s, op_s)(self._s))
            else:
                return self._from_pyseries(getattr(self._s, op_s)(_s))

        if isinstance(other, (PyDecimal, int)) and self.dtype.is_decimal():
            _s = sequence_to_pyseries(self.name, [other], dtype=Decimal)

            if "rhs" in op_ffi:
                return self._from_pyseries(getattr(_s, op_s)(self._s))
            else:
                return self._from_pyseries(getattr(self._s, op_s)(_s))
        else:
            other = maybe_cast(other, self.dtype)
            f = get_ffi_func(op_ffi, self.dtype, self._s)
        if f is None:
            msg = (
                f"cannot do arithmetic with Series of dtype: {self.dtype!r} and argument"
                f" of type: {type(other).__name__!r}"
            )
            raise TypeError(msg)
        return self._from_pyseries(f(other))

    @overload
    def __add__(self, other: DataFrame) -> DataFrame:  # type: ignore[overload-overlap]
        ...

    @overload
    def __add__(self, other: Expr) -> Expr:  # type: ignore[overload-overlap]
        ...

    @overload
    def __add__(self, other: Any) -> Self: ...

    def __add__(self, other: Any) -> Self | DataFrame | Expr:
        if isinstance(other, str):
            other = Series("", [other])
        elif isinstance(other, pl.DataFrame):
            return other + self
        elif isinstance(other, pl.Expr):
            return F.lit(self) + other
        return self._arithmetic(other, "add", "add_<>")

    @overload
    def __sub__(self, other: Expr) -> Expr:  # type: ignore[overload-overlap]
        ...

    @overload
    def __sub__(self, other: Any) -> Self: ...

    def __sub__(self, other: Any) -> Self | Expr:
        if isinstance(other, pl.Expr):
            return F.lit(self) - other
        return self._arithmetic(other, "sub", "sub_<>")

    @overload
    def __truediv__(self, other: Expr) -> Expr:  # type: ignore[overload-overlap]
        ...

    @overload
    def __truediv__(self, other: Any) -> Series: ...

    def __truediv__(self, other: Any) -> Series | Expr:
        if isinstance(other, pl.Expr):
            return F.lit(self) / other
        if self.dtype.is_temporal():
            msg = "first cast to integer before dividing datelike dtypes"
            raise TypeError(msg)

        # this branch is exactly the floordiv function without rounding the floats
        if self.dtype.is_float() or self.dtype == Decimal:
            return self._arithmetic(other, "div", "div_<>")

        return self.cast(Float64) / other

    @overload
    def __floordiv__(self, other: Expr) -> Expr:  # type: ignore[overload-overlap]
        ...

    @overload
    def __floordiv__(self, other: Any) -> Series: ...

    def __floordiv__(self, other: Any) -> Series | Expr:
        if isinstance(other, pl.Expr):
            return F.lit(self) // other
        if self.dtype.is_temporal():
            msg = "first cast to integer before dividing datelike dtypes"
            raise TypeError(msg)

        if not isinstance(other, pl.Expr):
            other = F.lit(other)
        return self.to_frame().select_seq(F.col(self.name) // other).to_series()

    def __invert__(self) -> Series:
        return self.not_()

    @overload
    def __mul__(self, other: Expr) -> Expr:  # type: ignore[overload-overlap]
        ...

    @overload
    def __mul__(self, other: DataFrame) -> DataFrame:  # type: ignore[overload-overlap]
        ...

    @overload
    def __mul__(self, other: Any) -> Series: ...

    def __mul__(self, other: Any) -> Series | DataFrame | Expr:
        if isinstance(other, pl.Expr):
            return F.lit(self) * other
        if self.dtype.is_temporal():
            msg = "first cast to integer before multiplying datelike dtypes"
            raise TypeError(msg)
        elif isinstance(other, pl.DataFrame):
            return other * self
        else:
            return self._arithmetic(other, "mul", "mul_<>")

    @overload
    def __mod__(self, other: Expr) -> Expr:  # type: ignore[overload-overlap]
        ...

    @overload
    def __mod__(self, other: Any) -> Series: ...

    def __mod__(self, other: Any) -> Series | Expr:
        if isinstance(other, pl.Expr):
            return F.lit(self).__mod__(other)
        if self.dtype.is_temporal():
            msg = "first cast to integer before applying modulo on datelike dtypes"
            raise TypeError(msg)
        return self._arithmetic(other, "rem", "rem_<>")

    def __rmod__(self, other: Any) -> Series:
        if self.dtype.is_temporal():
            msg = "first cast to integer before applying modulo on datelike dtypes"
            raise TypeError(msg)
        return self._arithmetic(other, "rem", "rem_<>_rhs")

    def __radd__(self, other: Any) -> Series:
        if isinstance(other, str):
            return (other + self.to_frame()).to_series()
        return self._arithmetic(other, "add", "add_<>_rhs")

    def __rsub__(self, other: Any) -> Series:
        return self._arithmetic(other, "sub", "sub_<>_rhs")

    def __rtruediv__(self, other: Any) -> Series:
        if self.dtype.is_temporal():
            msg = "first cast to integer before dividing datelike dtypes"
            raise TypeError(msg)
        if self.dtype.is_float():
            self.__rfloordiv__(other)

        if isinstance(other, int):
            other = float(other)
        return self.cast(Float64).__rfloordiv__(other)

    def __rfloordiv__(self, other: Any) -> Series:
        if self.dtype.is_temporal():
            msg = "first cast to integer before dividing datelike dtypes"
            raise TypeError(msg)
        return self._arithmetic(other, "div", "div_<>_rhs")

    def __rmul__(self, other: Any) -> Series:
        if self.dtype.is_temporal():
            msg = "first cast to integer before multiplying datelike dtypes"
            raise TypeError(msg)
        return self._arithmetic(other, "mul", "mul_<>")

    def __pow__(self, exponent: int | float | Series) -> Series:
        return self.pow(exponent)

    def __rpow__(self, other: Any) -> Series:
        return self.to_frame().select_seq(other ** F.col(self.name)).to_series()

    def __matmul__(self, other: Any) -> float | Series | None:
        if isinstance(other, Sequence) or (
            _check_for_numpy(other) and isinstance(other, np.ndarray)
        ):
            other = Series(other)
        # elif isinstance(other, pl.DataFrame):
        #     return other.__rmatmul__(self)  # type: ignore[return-value]
        return self.dot(other)

    def __rmatmul__(self, other: Any) -> float | Series | None:
        if isinstance(other, Sequence) or (
            _check_for_numpy(other) and isinstance(other, np.ndarray)
        ):
            other = Series(other)
        return other.dot(self)

    def __neg__(self) -> Series:
        return self.to_frame().select_seq(-F.col(self.name)).to_series()

    def __pos__(self) -> Series:
        return self

    def __abs__(self) -> Series:
        return self.abs()

    def __copy__(self) -> Self:
        return self.clone()

    def __deepcopy__(self, memo: None = None) -> Self:
        return self.clone()

    def __contains__(self, item: Any) -> bool:
        if item is None:
            return self.null_count() > 0
        return self.implode().list.contains(item).item()

    def __iter__(self) -> Generator[Any, None, None]:
        if self.dtype in (List, Array):
            # TODO: either make a change and return py-native list data here, or find
            #  a faster way to return nested/List series; sequential 'get_index' calls
            #  make this path a lot slower (~10x) than it needs to be.
            get_index = self._s.get_index
            for idx in range(self.len()):
                yield get_index(idx)
        else:
            buffer_size = 25_000
            for offset in range(0, self.len(), buffer_size):
                yield from self.slice(offset, buffer_size).to_list()

    def _pos_idxs(self, size: int) -> Series:
        # Unsigned or signed Series (ordered from fastest to slowest).
        #   - pl.UInt32 (polars) or pl.UInt64 (polars_u64_idx) Series indexes.
        #   - Other unsigned Series indexes are converted to pl.UInt32 (polars)
        #     or pl.UInt64 (polars_u64_idx).
        #   - Signed Series indexes are converted pl.UInt32 (polars) or
        #     pl.UInt64 (polars_u64_idx) after negative indexes are converted
        #     to absolute indexes.

        # pl.UInt32 (polars) or pl.UInt64 (polars_u64_idx).
        idx_type = get_index_type()

        if self.dtype == idx_type:
            return self

        if not self.dtype.is_integer():
            msg = "unsupported idxs datatype"
            raise NotImplementedError(msg)

        if self.len() == 0:
            return Series(self.name, [], dtype=idx_type)

        if idx_type == UInt32:
            if self.dtype in {Int64, UInt64}:
                if self.max() >= 2**32:  # type: ignore[operator]
                    msg = "index positions should be smaller than 2^32"
                    raise ValueError(msg)
            if self.dtype == Int64:
                if self.min() < -(2**32):  # type: ignore[operator]
                    msg = "index positions should be bigger than -2^32 + 1"
                    raise ValueError(msg)

        if self.dtype.is_signed_integer():
            if self.min() < 0:  # type: ignore[operator]
                if idx_type == UInt32:
                    idxs = self.cast(Int32) if self.dtype in {Int8, Int16} else self
                else:
                    idxs = (
                        self.cast(Int64) if self.dtype in {Int8, Int16, Int32} else self
                    )

                # Update negative indexes to absolute indexes.
                return (
                    idxs.to_frame()
                    .select(
                        F.when(F.col(idxs.name) < 0)
                        .then(size + F.col(idxs.name))
                        .otherwise(F.col(idxs.name))
                        .cast(idx_type)
                    )
                    .to_series(0)
                )

        return self.cast(idx_type)

    def _take_with_series(self, s: Series) -> Series:
        return self._from_pyseries(self._s.take_with_series(s._s))

    @overload
    def __getitem__(self, item: int) -> Any: ...

    @overload
    def __getitem__(
        self,
        item: Series | range | slice | np.ndarray[Any, Any] | list[int],
    ) -> Series: ...

    def __getitem__(
        self,
        item: (int | Series | range | slice | np.ndarray[Any, Any] | list[int]),
    ) -> Any:
        if isinstance(item, Series) and item.dtype.is_integer():
            return self._take_with_series(item._pos_idxs(self.len()))

        elif _check_for_numpy(item) and isinstance(item, np.ndarray):
            return self._take_with_series(numpy_to_idxs(item, self.len()))

        # Integer
        elif isinstance(item, int):
            return self._s.get_index_signed(item)

        # Slice
        elif isinstance(item, slice):
            return PolarsSlice(self).apply(item)

        # Range
        elif isinstance(item, range):
            return self[range_to_slice(item)]

        # Sequence of integers (also triggers on empty sequence)
        elif isinstance(item, Sequence) and (
            not item or (isinstance(item[0], int) and not isinstance(item[0], bool))  # type: ignore[redundant-expr]
        ):
            idx_series = Series("", item, dtype=Int64)._pos_idxs(self.len())
            if idx_series.has_validity():
                msg = "cannot use `__getitem__` with index values containing nulls"
                raise ValueError(msg)
            return self._take_with_series(idx_series)

        msg = (
            f"cannot use `__getitem__` on Series of dtype {self.dtype!r}"
            f" with argument {item!r} of type {type(item).__name__!r}"
        )
        raise TypeError(msg)

    def __setitem__(
        self,
        key: int | Series | np.ndarray[Any, Any] | Sequence[object] | tuple[object],
        value: Any,
    ) -> None:
        # do the single idx as first branch as those are likely in a tight loop
        if isinstance(key, int) and not isinstance(key, bool):
            self.scatter(key, value)
            return None
        elif isinstance(value, Sequence) and not isinstance(value, str):
            if self.dtype.is_numeric() or self.dtype.is_temporal():
                self.scatter(key, value)  # type: ignore[arg-type]
                return None
            msg = (
                f"cannot set Series of dtype: {self.dtype!r} with list/tuple as value;"
                " use a scalar value"
            )
            raise TypeError(msg)
        if isinstance(key, Series):
            if key.dtype == Boolean:
                self._s = self.set(key, value)._s
            elif key.dtype == UInt64:
                self._s = self.scatter(key.cast(UInt32), value)._s
            elif key.dtype == UInt32:
                self._s = self.scatter(key, value)._s

        # TODO: implement for these types without casting to series
        elif _check_for_numpy(key) and isinstance(key, np.ndarray):
            if key.dtype == np.bool_:
                # boolean numpy mask
                self._s = self.scatter(np.argwhere(key)[:, 0], value)._s
            else:
                s = self._from_pyseries(
                    PySeries.new_u32("", np.array(key, np.uint32), _strict=True)
                )
                self.__setitem__(s, value)
        elif isinstance(key, (list, tuple)):
            s = self._from_pyseries(sequence_to_pyseries("", key, dtype=UInt32))
            self.__setitem__(s, value)
        else:
            msg = f'cannot use "{key!r}" for indexing'
            raise TypeError(msg)

    def __array__(self, dtype: Any | None = None) -> np.ndarray[Any, Any]:
        """
        Numpy __array__ interface protocol.

        Ensures that `np.asarray(pl.Series(..))` works as expected, see
        https://numpy.org/devdocs/user/basics.interoperability.html#the-array-method.
        """
        if dtype is None and self.null_count() == 0 and self.dtype == String:
            dtype = np.dtype("U")

        if dtype:
            return self.to_numpy().__array__(dtype)
        else:
            return self.to_numpy().__array__()

    def __array_ufunc__(
        self, ufunc: np.ufunc, method: str, *inputs: Any, **kwargs: Any
    ) -> Series:
        """Numpy universal functions."""
        if self._s.n_chunks() > 1:
            self._s.rechunk(in_place=True)

        s = self._s

        if method == "__call__":
            if ufunc.nout != 1:
                msg = "only ufuncs that return one 1D array are supported"
                raise NotImplementedError(msg)

            args: list[int | float | np.ndarray[Any, Any]] = []

            validity_mask = self.is_not_null()
            for arg in inputs:
                if isinstance(arg, (int, float, np.ndarray)):
                    args.append(arg)
                elif isinstance(arg, Series):
                    validity_mask &= arg.is_not_null()
                    args.append(arg.to_physical()._s.to_numpy_view())
                else:
                    msg = f"unsupported type {type(arg).__name__!r} for {arg!r}"
                    raise TypeError(msg)

            # Get minimum dtype needed to be able to cast all input arguments to the
            # same dtype.
            dtype_char_minimum = np.result_type(*args).char

            # Get all possible output dtypes for ufunc.
            # Input dtypes and output dtypes seem to always match for ufunc.types,
            # so pick all the different output dtypes.
            dtypes_ufunc = [
                input_output_type[-1]
                for input_output_type in ufunc.types
                if supported_numpy_char_code(input_output_type[-1])
            ]

            # Get the first ufunc dtype from all possible ufunc dtypes for which
            # the input arguments can be safely cast to that ufunc dtype.
            for dtype_ufunc in dtypes_ufunc:
                if np.can_cast(dtype_char_minimum, dtype_ufunc):
                    dtype_char_minimum = dtype_ufunc
                    break

            # Override minimum dtype if requested.
            dtype_char = (
                np.dtype(kwargs.pop("dtype")).char
                if "dtype" in kwargs
                else dtype_char_minimum
            )

            f = get_ffi_func("apply_ufunc_<>", numpy_char_code_to_dtype(dtype_char), s)

            if f is None:
                msg = (
                    "could not find "
                    f"`apply_ufunc_{numpy_char_code_to_dtype(dtype_char)}`"
                )
                raise NotImplementedError(msg)

            series = f(lambda out: ufunc(*args, out=out, dtype=dtype_char, **kwargs))
            return (
                self._from_pyseries(series)
                .to_frame()
                .select(F.when(validity_mask).then(F.col(self.name)))
                .to_series(0)
            )
        else:
            msg = (
                "only `__call__` is implemented for numpy ufuncs on a Series, got "
                f"`{method!r}`"
            )
            raise NotImplementedError(msg)

    def _repr_html_(self) -> str:
        """Format output data in HTML for display in Jupyter Notebooks."""
        return self.to_frame()._repr_html_(_from_series=True)

    @deprecate_renamed_parameter("row", "index", version="0.19.3")
    def item(self, index: int | None = None) -> Any:
        """
        Return the Series as a scalar, or return the element at the given index.

        If no index is provided, this is equivalent to `s[0]`, with a check
        that the shape is (1,). With an index, this is equivalent to `s[index]`.

        Examples
        --------
        >>> s1 = pl.Series("a", [1])
        >>> s1.item()
        1
        >>> s2 = pl.Series("a", [9, 8, 7])
        >>> s2.cum_sum().item(-1)
        24
        """
        if index is None:
            if len(self) != 1:
                msg = (
                    "can only call '.item()' if the Series is of length 1,"
                    f" or an explicit index is provided (Series is of length {len(self)})"
                )
                raise ValueError(msg)
            return self._s.get_index(0)

        return self._s.get_index_signed(index)

    def estimated_size(self, unit: SizeUnit = "b") -> int | float:
        """
        Return an estimation of the total (heap) allocated size of the Series.

        Estimated size is given in the specified unit (bytes by default).

        This estimation is the sum of the size of its buffers, validity, including
        nested arrays. Multiple arrays may share buffers and bitmaps. Therefore, the
        size of 2 arrays is not the sum of the sizes computed from this function. In
        particular, [`StructArray`]'s size is an upper bound.

        When an array is sliced, its allocated size remains constant because the buffer
        unchanged. However, this function will yield a smaller number. This is because
        this function returns the visible size of the buffer, not its total capacity.

        FFI buffers are included in this estimation.

        Parameters
        ----------
        unit : {'b', 'kb', 'mb', 'gb', 'tb'}
            Scale the returned size to the given unit.

        Examples
        --------
        >>> s = pl.Series("values", list(range(1_000_000)), dtype=pl.UInt32)
        >>> s.estimated_size()
        4000000
        >>> s.estimated_size("mb")
        3.814697265625
        """
        sz = self._s.estimated_size()
        return scale_bytes(sz, unit)

    def sqrt(self) -> Series:
        """
        Compute the square root of the elements.

        Syntactic sugar for

        >>> pl.Series([1, 2]) ** 0.5
        shape: (2,)
        Series: '' [f64]
        [
            1.0
            1.414214
        ]

        Examples
        --------
        >>> s = pl.Series([1, 2, 3])
        >>> s.sqrt()
        shape: (3,)
        Series: '' [f64]
        [
            1.0
            1.414214
            1.732051
        ]
        """

    def cbrt(self) -> Series:
        """
        Compute the cube root of the elements.

        Optimization for

        >>> pl.Series([1, 2]) ** (1.0 / 3)
        shape: (2,)
        Series: '' [f64]
        [
            1.0
            1.259921
        ]

        Examples
        --------
        >>> s = pl.Series([1, 2, 3])
        >>> s.cbrt()
        shape: (3,)
        Series: '' [f64]
        [
            1.0
            1.259921
            1.44225
        ]
        """

    @overload
    def any(self, *, ignore_nulls: Literal[True] = ...) -> bool: ...

    @overload
    def any(self, *, ignore_nulls: bool) -> bool | None: ...

    @deprecate_renamed_parameter("drop_nulls", "ignore_nulls", version="0.19.0")
    def any(self, *, ignore_nulls: bool = True) -> bool | None:
        """
        Return whether any of the values in the column are `True`.

        Only works on columns of data type :class:`Boolean`.

        Parameters
        ----------
        ignore_nulls
            Ignore null values (default).

            If set to `False`, `Kleene logic`_ is used to deal with nulls:
            if the column contains any null values and no `True` values,
            the output is `None`.

            .. _Kleene logic: https://en.wikipedia.org/wiki/Three-valued_logic

        Returns
        -------
        bool or None

        Examples
        --------
        >>> pl.Series([True, False]).any()
        True
        >>> pl.Series([False, False]).any()
        False
        >>> pl.Series([None, False]).any()
        False

        Enable Kleene logic by setting `ignore_nulls=False`.

        >>> pl.Series([None, False]).any(ignore_nulls=False)  # Returns None
        """
        return self._s.any(ignore_nulls=ignore_nulls)

    @overload
    def all(self, *, ignore_nulls: Literal[True] = ...) -> bool: ...

    @overload
    def all(self, *, ignore_nulls: bool) -> bool | None: ...

    @deprecate_renamed_parameter("drop_nulls", "ignore_nulls", version="0.19.0")
    def all(self, *, ignore_nulls: bool = True) -> bool | None:
        """
        Return whether all values in the column are `True`.

        Only works on columns of data type :class:`Boolean`.

        Parameters
        ----------
        ignore_nulls
            Ignore null values (default).

            If set to `False`, `Kleene logic`_ is used to deal with nulls:
            if the column contains any null values and no `False` values,
            the output is `None`.

            .. _Kleene logic: https://en.wikipedia.org/wiki/Three-valued_logic

        Returns
        -------
        bool or None

        Examples
        --------
        >>> pl.Series([True, True]).all()
        True
        >>> pl.Series([False, True]).all()
        False
        >>> pl.Series([None, True]).all()
        True

        Enable Kleene logic by setting `ignore_nulls=False`.

        >>> pl.Series([None, True]).all(ignore_nulls=False)  # Returns None
        """
        return self._s.all(ignore_nulls=ignore_nulls)

    def log(self, base: float = math.e) -> Series:
        """
        Compute the logarithm to a given base.

        Examples
        --------
        >>> s = pl.Series([1, 2, 3])
        >>> s.log()
        shape: (3,)
        Series: '' [f64]
        [
            0.0
            0.693147
            1.098612
        ]
        """

    def log1p(self) -> Series:
        """
        Compute the natural logarithm of the input array plus one, element-wise.

        Examples
        --------
        >>> s = pl.Series([1, 2, 3])
        >>> s.log1p()
        shape: (3,)
        Series: '' [f64]
        [
            0.693147
            1.098612
            1.386294
        ]
        """

    def log10(self) -> Series:
        """
        Compute the base 10 logarithm of the input array, element-wise.

        Examples
        --------
        >>> s = pl.Series([10, 100, 1000])
        >>> s.log10()
        shape: (3,)
        Series: '' [f64]
        [
            1.0
            2.0
            3.0
        ]
        """

    def exp(self) -> Series:
        """
        Compute the exponential, element-wise.

        Examples
        --------
        >>> s = pl.Series([1, 2, 3])
        >>> s.exp()
        shape: (3,)
        Series: '' [f64]
        [
            2.718282
            7.389056
            20.085537
        ]
        """

    def drop_nulls(self) -> Series:
        """
        Drop all null values.

        The original order of the remaining elements is preserved.

        See Also
        --------
        drop_nans

        Notes
        -----
        A null value is not the same as a NaN value.
        To drop NaN values, use :func:`drop_nans`.

        Examples
        --------
        >>> s = pl.Series([1.0, None, 3.0, float("nan")])
        >>> s.drop_nulls()
        shape: (3,)
        Series: '' [f64]
        [
                1.0
                3.0
                NaN
        ]
        """

    def drop_nans(self) -> Series:
        """
        Drop all floating point NaN values.

        The original order of the remaining elements is preserved.

        See Also
        --------
        drop_nulls

        Notes
        -----
        A NaN value is not the same as a null value.
        To drop null values, use :func:`drop_nulls`.

        Examples
        --------
        >>> s = pl.Series([1.0, None, 3.0, float("nan")])
        >>> s.drop_nans()
        shape: (3,)
        Series: '' [f64]
        [
                1.0
                null
                3.0
        ]
        """

    def to_frame(self, name: str | None = None) -> DataFrame:
        """
        Cast this Series to a DataFrame.

        Parameters
        ----------
        name
            optionally name/rename the Series column in the new DataFrame.

        Examples
        --------
        >>> s = pl.Series("a", [123, 456])
        >>> df = s.to_frame()
        >>> df
        shape: (2, 1)
        ┌─────┐
        │ a   │
        │ --- │
        │ i64 │
        ╞═════╡
        │ 123 │
        │ 456 │
        └─────┘

        >>> df = s.to_frame("xyz")
        >>> df
        shape: (2, 1)
        ┌─────┐
        │ xyz │
        │ --- │
        │ i64 │
        ╞═════╡
        │ 123 │
        │ 456 │
        └─────┘
        """
        if isinstance(name, str):
            return wrap_df(PyDataFrame([self.rename(name)._s]))
        return wrap_df(PyDataFrame([self._s]))

    def describe(
        self,
        percentiles: Sequence[float] | float | None = (0.25, 0.50, 0.75),
        interpolation: RollingInterpolationMethod = "nearest",
    ) -> DataFrame:
        """
        Quick summary statistics of a Series.

        Series with mixed datatypes will return summary statistics for the datatype of
        the first value.

        Parameters
        ----------
        percentiles
            One or more percentiles to include in the summary statistics (if the
            Series has a numeric dtype). All values must be in the range `[0, 1]`.
        interpolation : {'nearest', 'higher', 'lower', 'midpoint', 'linear'}
            Interpolation method used when calculating percentiles.

        Notes
        -----
        The median is included by default as the 50% percentile.

        Returns
        -------
        DataFrame
            Mapping with summary statistics of a Series.

        Examples
        --------
        >>> s = pl.Series([1, 2, 3, 4, 5])
        >>> s.describe()
        shape: (9, 2)
        ┌────────────┬──────────┐
        │ statistic  ┆ value    │
        │ ---        ┆ ---      │
        │ str        ┆ f64      │
        ╞════════════╪══════════╡
        │ count      ┆ 5.0      │
        │ null_count ┆ 0.0      │
        │ mean       ┆ 3.0      │
        │ std        ┆ 1.581139 │
        │ min        ┆ 1.0      │
        │ 25%        ┆ 2.0      │
        │ 50%        ┆ 3.0      │
        │ 75%        ┆ 4.0      │
        │ max        ┆ 5.0      │
        └────────────┴──────────┘

        Non-numeric data types may not have all statistics available.

        >>> s = pl.Series(["aa", "aa", None, "bb", "cc"])
        >>> s.describe()
        shape: (4, 2)
        ┌────────────┬───────┐
        │ statistic  ┆ value │
        │ ---        ┆ ---   │
        │ str        ┆ str   │
        ╞════════════╪═══════╡
        │ count      ┆ 4     │
        │ null_count ┆ 1     │
        │ min        ┆ aa    │
        │ max        ┆ cc    │
        └────────────┴───────┘
        """
        stats = self.to_frame().describe(
            percentiles=percentiles,
            interpolation=interpolation,
        )
        stats.columns = ["statistic", "value"]
        return stats.filter(F.col("value").is_not_null())

    def sum(self) -> int | float:
        """
        Reduce this Series to the sum value.

        Notes
        -----
        Dtypes in {Int8, UInt8, Int16, UInt16} are cast to
        Int64 before summing to prevent overflow issues.

        Examples
        --------
        >>> s = pl.Series("a", [1, 2, 3])
        >>> s.sum()
        6
        """
        return self._s.sum()

    def mean(self) -> PythonLiteral | None:
        """
        Reduce this Series to the mean value.

        Examples
        --------
        >>> s = pl.Series("a", [1, 2, 3])
        >>> s.mean()
        2.0
        """
        return self._s.mean()

    def product(self) -> int | float:
        """
        Reduce this Series to the product value.

        Examples
        --------
        >>> s = pl.Series("a", [1, 2, 3])
        >>> s.product()
        6
        """
        return self._s.product()

    def pow(self, exponent: int | float | Series) -> Series:
        """
        Raise to the power of the given exponent.

        Parameters
        ----------
        exponent
            The exponent. Accepts Series input.

        Examples
        --------
        >>> s = pl.Series("foo", [1, 2, 3, 4])
        >>> s.pow(3)
        shape: (4,)
        Series: 'foo' [i64]
        [
            1
            8
            27
            64
        ]
        """
        if _check_for_numpy(exponent) and isinstance(exponent, np.ndarray):
            exponent = Series(exponent)
        return self.to_frame().select_seq(F.col(self.name).pow(exponent)).to_series()

    def min(self) -> PythonLiteral | None:
        """
        Get the minimal value in this Series.

        Examples
        --------
        >>> s = pl.Series("a", [1, 2, 3])
        >>> s.min()
        1
        """
        return self._s.min()

    def max(self) -> PythonLiteral | None:
        """
        Get the maximum value in this Series.

        Examples
        --------
        >>> s = pl.Series("a", [1, 2, 3])
        >>> s.max()
        3
        """
        return self._s.max()

    def nan_max(self) -> int | float | date | datetime | timedelta | str:
        """
        Get maximum value, but propagate/poison encountered NaN values.

        This differs from numpy's `nanmax` as numpy defaults to propagating NaN values,
        whereas polars defaults to ignoring them.

        Examples
        --------
        >>> s = pl.Series("a", [1, 3, 4])
        >>> s.nan_max()
        4

        >>> s = pl.Series("a", [1, float("nan"), 4])
        >>> s.nan_max()
        nan
        """
        return self.to_frame().select_seq(F.col(self.name).nan_max()).item()

    def nan_min(self) -> int | float | date | datetime | timedelta | str:
        """
        Get minimum value, but propagate/poison encountered NaN values.

        This differs from numpy's `nanmax` as numpy defaults to propagating NaN values,
        whereas polars defaults to ignoring them.

        Examples
        --------
        >>> s = pl.Series("a", [1, 3, 4])
        >>> s.nan_min()
        1

        >>> s = pl.Series("a", [1, float("nan"), 4])
        >>> s.nan_min()
        nan
        """
        return self.to_frame().select_seq(F.col(self.name).nan_min()).item()

    def std(self, ddof: int = 1) -> float | timedelta | None:
        """
        Get the standard deviation of this Series.

        Parameters
        ----------
        ddof
            “Delta Degrees of Freedom”: the divisor used in the calculation is N - ddof,
            where N represents the number of elements.
            By default ddof is 1.

        Examples
        --------
        >>> s = pl.Series("a", [1, 2, 3])
        >>> s.std()
        1.0
        """
        return self._s.std(ddof)

    def var(self, ddof: int = 1) -> float | timedelta | None:
        """
        Get variance of this Series.

        Parameters
        ----------
        ddof
            “Delta Degrees of Freedom”: the divisor used in the calculation is N - ddof,
            where N represents the number of elements.
            By default ddof is 1.

        Examples
        --------
        >>> s = pl.Series("a", [1, 2, 3])
        >>> s.var()
        1.0
        """
        return self._s.var(ddof)

    def median(self) -> PythonLiteral | None:
        """
        Get the median of this Series.

        Examples
        --------
        >>> s = pl.Series("a", [1, 2, 3])
        >>> s.median()
        2.0
        """
        return self._s.median()

    def quantile(
        self, quantile: float, interpolation: RollingInterpolationMethod = "nearest"
    ) -> float | None:
        """
        Get the quantile value of this Series.

        Parameters
        ----------
        quantile
            Quantile between 0.0 and 1.0.
        interpolation : {'nearest', 'higher', 'lower', 'midpoint', 'linear'}
            Interpolation method.

        Examples
        --------
        >>> s = pl.Series("a", [1, 2, 3])
        >>> s.quantile(0.5)
        2.0
        """
        return self._s.quantile(quantile, interpolation)

    def to_dummies(
        self, *, separator: str = "_", drop_first: bool = False
    ) -> DataFrame:
        """
        Get dummy/indicator variables.

        Parameters
        ----------
        separator
            Separator/delimiter used when generating column names.
        drop_first
            Remove the first category from the variable being encoded.

        Examples
        --------
        >>> s = pl.Series("a", [1, 2, 3])
        >>> s.to_dummies()
        shape: (3, 3)
        ┌─────┬─────┬─────┐
        │ a_1 ┆ a_2 ┆ a_3 │
        │ --- ┆ --- ┆ --- │
        │ u8  ┆ u8  ┆ u8  │
        ╞═════╪═════╪═════╡
        │ 1   ┆ 0   ┆ 0   │
        │ 0   ┆ 1   ┆ 0   │
        │ 0   ┆ 0   ┆ 1   │
        └─────┴─────┴─────┘

        >>> s.to_dummies(drop_first=True)
        shape: (3, 2)
        ┌─────┬─────┐
        │ a_2 ┆ a_3 │
        │ --- ┆ --- │
        │ u8  ┆ u8  │
        ╞═════╪═════╡
        │ 0   ┆ 0   │
        │ 1   ┆ 0   │
        │ 0   ┆ 1   │
        └─────┴─────┘
        """
        return wrap_df(self._s.to_dummies(separator, drop_first))

    @overload
    def cut(
        self,
        breaks: Sequence[float],
        labels: Sequence[str] | None = ...,
        break_point_label: str = ...,
        category_label: str = ...,
        *,
        left_closed: bool = ...,
        include_breaks: bool = ...,
        as_series: Literal[True] = ...,
    ) -> Series: ...

    @overload
    def cut(
        self,
        breaks: Sequence[float],
        labels: Sequence[str] | None = ...,
        break_point_label: str = ...,
        category_label: str = ...,
        *,
        left_closed: bool = ...,
        include_breaks: bool = ...,
        as_series: Literal[False],
    ) -> DataFrame: ...

    @overload
    def cut(
        self,
        breaks: Sequence[float],
        labels: Sequence[str] | None = ...,
        break_point_label: str = ...,
        category_label: str = ...,
        *,
        left_closed: bool = ...,
        include_breaks: bool = ...,
        as_series: bool,
    ) -> Series | DataFrame: ...

    @deprecate_nonkeyword_arguments(["self", "breaks"], version="0.19.0")
    @deprecate_renamed_parameter("series", "as_series", version="0.19.0")
    @unstable()
    def cut(
        self,
        breaks: Sequence[float],
        labels: Sequence[str] | None = None,
        break_point_label: str = "break_point",
        category_label: str = "category",
        *,
        left_closed: bool = False,
        include_breaks: bool = False,
        as_series: bool = True,
    ) -> Series | DataFrame:
        """
        Bin continuous values into discrete categories.

        .. warning::
            This functionality is considered **unstable**. It may be changed
            at any point without it being considered a breaking change.

        Parameters
        ----------
        breaks
            List of unique cut points.
        labels
            Names of the categories. The number of labels must be equal to the number
            of cut points plus one.
        break_point_label
            Name of the breakpoint column. Only used if `include_breaks` is set to
            `True`.

            .. deprecated:: 0.19.0
                This parameter will be removed. Use `Series.struct.rename_fields` to
                rename the field instead.
        category_label
            Name of the category column. Only used if `include_breaks` is set to
            `True`.

            .. deprecated:: 0.19.0
                This parameter will be removed. Use `Series.struct.rename_fields` to
                rename the field instead.
        left_closed
            Set the intervals to be left-closed instead of right-closed.
        include_breaks
            Include a column with the right endpoint of the bin each observation falls
            in. This will change the data type of the output from a
            :class:`Categorical` to a :class:`Struct`.
        as_series
            If set to `False`, return a DataFrame containing the original values,
            the breakpoints, and the categories.

            .. deprecated:: 0.19.0
                This parameter will be removed. The same behavior can be achieved by
                setting `include_breaks=True`, unnesting the resulting struct Series,
                and adding the result to the original Series.

        Returns
        -------
        Series
            Series of data type :class:`Categorical` if `include_breaks` is set to
            `False` (default), otherwise a Series of data type :class:`Struct`.

        See Also
        --------
        qcut

        Examples
        --------
        Divide the column into three categories.

        >>> s = pl.Series("foo", [-2, -1, 0, 1, 2])
        >>> s.cut([-1, 1], labels=["a", "b", "c"])
        shape: (5,)
        Series: 'foo' [cat]
        [
                "a"
                "a"
                "b"
                "b"
                "c"
        ]

        Create a DataFrame with the breakpoint and category for each value.

        >>> cut = s.cut([-1, 1], include_breaks=True).alias("cut")
        >>> s.to_frame().with_columns(cut).unnest("cut")
        shape: (5, 3)
        ┌─────┬─────────────┬────────────┐
        │ foo ┆ break_point ┆ category   │
        │ --- ┆ ---         ┆ ---        │
        │ i64 ┆ f64         ┆ cat        │
        ╞═════╪═════════════╪════════════╡
        │ -2  ┆ -1.0        ┆ (-inf, -1] │
        │ -1  ┆ -1.0        ┆ (-inf, -1] │
        │ 0   ┆ 1.0         ┆ (-1, 1]    │
        │ 1   ┆ 1.0         ┆ (-1, 1]    │
        │ 2   ┆ inf         ┆ (1, inf]   │
        └─────┴─────────────┴────────────┘
        """
        if break_point_label != "break_point":
            issue_deprecation_warning(
                "The `break_point_label` parameter for `Series.cut` will be removed."
                " Use `Series.struct.rename_fields` to rename the field instead.",
                version="0.19.0",
            )
        if category_label != "category":
            issue_deprecation_warning(
                "The `category_label` parameter for `Series.cut` will be removed."
                " Use `Series.struct.rename_fields` to rename the field instead.",
                version="0.19.0",
            )
        if not as_series:
            issue_deprecation_warning(
                "The `as_series` parameter for `Series.cut` will be removed."
                " The same behavior can be achieved by setting `include_breaks=True`,"
                " unnesting the resulting struct Series,"
                " and adding the result to the original Series.",
                version="0.19.0",
            )
            temp_name = self.name + "_bin"
            return (
                self.to_frame()
                .with_columns(
                    F.col(self.name)
                    .cut(
                        breaks,
                        labels=labels,
                        left_closed=left_closed,
                        include_breaks=True,  # always include breaks
                    )
                    .alias(temp_name)
                )
                .unnest(temp_name)
                .rename({"brk": break_point_label, temp_name: category_label})
            )

        result = (
            self.to_frame()
            .select_seq(
                F.col(self.name).cut(
                    breaks,
                    labels=labels,
                    left_closed=left_closed,
                    include_breaks=include_breaks,
                )
            )
            .to_series()
        )

        if include_breaks:
            result = result.struct.rename_fields([break_point_label, category_label])

        return result

    @overload
    def qcut(
        self,
        quantiles: Sequence[float] | int,
        *,
        labels: Sequence[str] | None = ...,
        left_closed: bool = ...,
        allow_duplicates: bool = ...,
        include_breaks: bool = ...,
        break_point_label: str = ...,
        category_label: str = ...,
        as_series: Literal[True] = ...,
    ) -> Series: ...

    @overload
    def qcut(
        self,
        quantiles: Sequence[float] | int,
        *,
        labels: Sequence[str] | None = ...,
        left_closed: bool = ...,
        allow_duplicates: bool = ...,
        include_breaks: bool = ...,
        break_point_label: str = ...,
        category_label: str = ...,
        as_series: Literal[False],
    ) -> DataFrame: ...

    @overload
    def qcut(
        self,
        quantiles: Sequence[float] | int,
        *,
        labels: Sequence[str] | None = ...,
        left_closed: bool = ...,
        allow_duplicates: bool = ...,
        include_breaks: bool = ...,
        break_point_label: str = ...,
        category_label: str = ...,
        as_series: bool,
    ) -> Series | DataFrame: ...

    @unstable()
    def qcut(
        self,
        quantiles: Sequence[float] | int,
        *,
        labels: Sequence[str] | None = None,
        left_closed: bool = False,
        allow_duplicates: bool = False,
        include_breaks: bool = False,
        break_point_label: str = "break_point",
        category_label: str = "category",
        as_series: bool = True,
    ) -> Series | DataFrame:
        """
        Bin continuous values into discrete categories based on their quantiles.

        .. warning::
            This functionality is considered **unstable**. It may be changed
            at any point without it being considered a breaking change.

        Parameters
        ----------
        quantiles
            Either a list of quantile probabilities between 0 and 1 or a positive
            integer determining the number of bins with uniform probability.
        labels
            Names of the categories. The number of labels must be equal to the number
            of cut points plus one.
        left_closed
            Set the intervals to be left-closed instead of right-closed.
        allow_duplicates
            If set to `True`, duplicates in the resulting quantiles are dropped,
            rather than raising a `DuplicateError`. This can happen even with unique
            probabilities, depending on the data.
        include_breaks
            Include a column with the right endpoint of the bin each observation falls
            in. This will change the data type of the output from a
            :class:`Categorical` to a :class:`Struct`.
        break_point_label
            Name of the breakpoint column. Only used if `include_breaks` is set to
            `True`.

            .. deprecated:: 0.19.0
                This parameter will be removed. Use `Series.struct.rename_fields` to
                rename the field instead.
        category_label
            Name of the category column. Only used if `include_breaks` is set to
            `True`.

            .. deprecated:: 0.19.0
                This parameter will be removed. Use `Series.struct.rename_fields` to
                rename the field instead.
        as_series
            If set to `False`, return a DataFrame containing the original values,
            the breakpoints, and the categories.

            .. deprecated:: 0.19.0
                This parameter will be removed. The same behavior can be achieved by
                setting `include_breaks=True`, unnesting the resulting struct Series,
                and adding the result to the original Series.

        Returns
        -------
        Series
            Series of data type :class:`Categorical` if `include_breaks` is set to
            `False` (default), otherwise a Series of data type :class:`Struct`.

        See Also
        --------
        cut

        Examples
        --------
        Divide a column into three categories according to pre-defined quantile
        probabilities.

        >>> s = pl.Series("foo", [-2, -1, 0, 1, 2])
        >>> s.qcut([0.25, 0.75], labels=["a", "b", "c"])
        shape: (5,)
        Series: 'foo' [cat]
        [
                "a"
                "a"
                "b"
                "b"
                "c"
        ]

        Divide a column into two categories using uniform quantile probabilities.

        >>> s.qcut(2, labels=["low", "high"], left_closed=True)
        shape: (5,)
        Series: 'foo' [cat]
        [
                "low"
                "low"
                "high"
                "high"
                "high"
        ]

        Create a DataFrame with the breakpoint and category for each value.

        >>> cut = s.qcut([0.25, 0.75], include_breaks=True).alias("cut")
        >>> s.to_frame().with_columns(cut).unnest("cut")
        shape: (5, 3)
        ┌─────┬─────────────┬────────────┐
        │ foo ┆ break_point ┆ category   │
        │ --- ┆ ---         ┆ ---        │
        │ i64 ┆ f64         ┆ cat        │
        ╞═════╪═════════════╪════════════╡
        │ -2  ┆ -1.0        ┆ (-inf, -1] │
        │ -1  ┆ -1.0        ┆ (-inf, -1] │
        │ 0   ┆ 1.0         ┆ (-1, 1]    │
        │ 1   ┆ 1.0         ┆ (-1, 1]    │
        │ 2   ┆ inf         ┆ (1, inf]   │
        └─────┴─────────────┴────────────┘
        """
        if break_point_label != "break_point":
            issue_deprecation_warning(
                "The `break_point_label` parameter for `Series.cut` will be removed."
                " Use `Series.struct.rename_fields` to rename the field instead.",
                version="0.19.0",
            )
        if category_label != "category":
            issue_deprecation_warning(
                "The `category_label` parameter for `Series.cut` will be removed."
                " Use `Series.struct.rename_fields` to rename the field instead.",
                version="0.19.0",
            )
        if not as_series:
            issue_deprecation_warning(
                "the `as_series` parameter for `Series.qcut` will be removed."
                " The same behavior can be achieved by setting `include_breaks=True`,"
                " unnesting the resulting struct Series,"
                " and adding the result to the original Series.",
                version="0.19.0",
            )
            temp_name = self.name + "_bin"
            return (
                self.to_frame()
                .with_columns(
                    F.col(self.name)
                    .qcut(
                        quantiles,
                        labels=labels,
                        left_closed=left_closed,
                        allow_duplicates=allow_duplicates,
                        include_breaks=True,  # always include breaks
                    )
                    .alias(temp_name)
                )
                .unnest(temp_name)
                .rename({"brk": break_point_label, temp_name: category_label})
            )

        result = (
            self.to_frame()
            .select(
                F.col(self.name).qcut(
                    quantiles,
                    labels=labels,
                    left_closed=left_closed,
                    allow_duplicates=allow_duplicates,
                    include_breaks=include_breaks,
                )
            )
            .to_series()
        )

        if include_breaks:
            result = result.struct.rename_fields([break_point_label, category_label])

        return result

    def rle(self) -> Series:
        """
        Compress the Series data using run-length encoding.

        Run-length encoding (RLE) encodes data by storing each *run* of identical values
        as a single value and its length.

        Returns
        -------
        Series
            Series of data type `Struct` with fields `lengths` of data type `Int32`
            and `values` of the original data type.

        Examples
        --------
        >>> s = pl.Series("s", [1, 1, 2, 1, None, 1, 3, 3])
        >>> s.rle().struct.unnest()
        shape: (6, 2)
        ┌─────────┬────────┐
        │ lengths ┆ values │
        │ ---     ┆ ---    │
        │ i32     ┆ i64    │
        ╞═════════╪════════╡
        │ 2       ┆ 1      │
        │ 1       ┆ 2      │
        │ 1       ┆ 1      │
        │ 1       ┆ null   │
        │ 1       ┆ 1      │
        │ 2       ┆ 3      │
        └─────────┴────────┘
        """

    def rle_id(self) -> Series:
        """
        Get a distinct integer ID for each run of identical values.

        The ID starts at 0 and increases by one each time the value of the column
        changes.

        Returns
        -------
        Series
            Series of data type `UInt32`.

        See Also
        --------
        rle

        Notes
        -----
        This functionality is especially useful for defining a new group for every time
        a column's value changes, rather than for every distinct value of that column.

        Examples
        --------
        >>> s = pl.Series("s", [1, 1, 2, 1, None, 1, 3, 3])
        >>> s.rle_id()
        shape: (8,)
        Series: 's' [u32]
        [
            0
            0
            1
            2
            3
            4
            5
            5
        ]
        """

    @unstable()
    def hist(
        self,
        bins: list[float] | None = None,
        *,
        bin_count: int | None = None,
        include_category: bool = True,
        include_breakpoint: bool = True,
    ) -> DataFrame:
        """
        Bin values into buckets and count their occurrences.

        .. warning::
            This functionality is considered **unstable**. It may be changed
            at any point without it being considered a breaking change.

        Parameters
        ----------
        bins
            Discretizations to make.
            If None given, we determine the boundaries based on the data.
        bin_count
            If no bins provided, this will be used to determine
            the distance of the bins
        include_breakpoint
            Include a column that indicates the upper breakpoint.
        include_category
            Include a column that shows the intervals as categories.

        Returns
        -------
        DataFrame

        Examples
        --------
        >>> a = pl.Series("a", [1, 3, 8, 8, 2, 1, 3])
        >>> a.hist(bin_count=4)
        shape: (5, 3)
        ┌─────────────┬─────────────┬───────┐
        │ break_point ┆ category    ┆ count │
        │ ---         ┆ ---         ┆ ---   │
        │ f64         ┆ cat         ┆ u32   │
        ╞═════════════╪═════════════╪═══════╡
        │ 0.0         ┆ (-inf, 0.0] ┆ 0     │
        │ 2.25        ┆ (0.0, 2.25] ┆ 3     │
        │ 4.5         ┆ (2.25, 4.5] ┆ 2     │
        │ 6.75        ┆ (4.5, 6.75] ┆ 0     │
        │ inf         ┆ (6.75, inf] ┆ 2     │
        └─────────────┴─────────────┴───────┘
        """
        out = (
            self.to_frame()
            .select_seq(
                F.col(self.name).hist(
                    bins=bins,
                    bin_count=bin_count,
                    include_category=include_category,
                    include_breakpoint=include_breakpoint,
                )
            )
            .to_series()
        )
        if not include_breakpoint and not include_category:
            return out.to_frame()
        else:
            return out.struct.unnest()

    def value_counts(self, *, sort: bool = False, parallel: bool = False) -> DataFrame:
        """
        Count the occurrences of unique values.

        Parameters
        ----------
        sort
            Sort the output by count in descending order.
            If set to `False` (default), the order of the output is random.
        parallel
            Execute the computation in parallel.

            .. note::
                This option should likely not be enabled in a group by context,
                as the computation is already parallelized per group.

        Returns
        -------
        DataFrame
            Mapping of unique values to their count.

        Examples
        --------
        >>> s = pl.Series("color", ["red", "blue", "red", "green", "blue", "blue"])
        >>> s.value_counts()  # doctest: +IGNORE_RESULT
        shape: (3, 2)
        ┌───────┬───────┐
        │ color ┆ count │
        │ ---   ┆ ---   │
        │ str   ┆ u32   │
        ╞═══════╪═══════╡
        │ red   ┆ 2     │
        │ green ┆ 1     │
        │ blue  ┆ 3     │
        └───────┴───────┘

        Sort the output by count.

        >>> s.value_counts(sort=True)
        shape: (3, 2)
        ┌───────┬───────┐
        │ color ┆ count │
        │ ---   ┆ ---   │
        │ str   ┆ u32   │
        ╞═══════╪═══════╡
        │ blue  ┆ 3     │
        │ red   ┆ 2     │
        │ green ┆ 1     │
        └───────┴───────┘
        """
        return pl.DataFrame._from_pydf(
            self._s.value_counts(sort=sort, parallel=parallel)
        )

    def unique_counts(self) -> Series:
        """
        Return a count of the unique values in the order of appearance.

        Examples
        --------
        >>> s = pl.Series("id", ["a", "b", "b", "c", "c", "c"])
        >>> s.unique_counts()
        shape: (3,)
        Series: 'id' [u32]
        [
            1
            2
            3
        ]
        """

    def entropy(self, base: float = math.e, *, normalize: bool = False) -> float | None:
        """
        Computes the entropy.

        Uses the formula `-sum(pk * log(pk)` where `pk` are discrete probabilities.

        Parameters
        ----------
        base
            Given base, defaults to `e`
        normalize
            Normalize pk if it doesn't sum to 1.

        Examples
        --------
        >>> a = pl.Series([0.99, 0.005, 0.005])
        >>> a.entropy(normalize=True)
        0.06293300616044681
        >>> b = pl.Series([0.65, 0.10, 0.25])
        >>> b.entropy(normalize=True)
        0.8568409950394724
        """
        return (
            self.to_frame()
            .select_seq(F.col(self.name).entropy(base, normalize=normalize))
            .to_series()
            .item()
        )

    @unstable()
    def cumulative_eval(
        self, expr: Expr, min_periods: int = 1, *, parallel: bool = False
    ) -> Series:
        """
        Run an expression over a sliding window that increases `1` slot every iteration.

        .. warning::
            This functionality is considered **unstable**. It may be changed
            at any point without it being considered a breaking change.

        Parameters
        ----------
        expr
            Expression to evaluate
        min_periods
            Number of valid values there should be in the window before the expression
            is evaluated. valid values = `length - null_count`
        parallel
            Run in parallel. Don't do this in a group by or another operation that
            already has much parallelization.

        Warnings
        --------
        This can be really slow as it can have `O(n^2)` complexity. Don't use this
        for operations that visit all elements.

        Examples
        --------
        >>> s = pl.Series("values", [1, 2, 3, 4, 5])
        >>> s.cumulative_eval(pl.element().first() - pl.element().last() ** 2)
        shape: (5,)
        Series: 'values' [i64]
        [
            0
            -3
            -8
            -15
            -24
        ]
        """

    def alias(self, name: str) -> Series:
        """
        Rename the series.

        Parameters
        ----------
        name
            The new name.

        Examples
        --------
        >>> s = pl.Series("a", [1, 2, 3])
        >>> s.alias("b")
        shape: (3,)
        Series: 'b' [i64]
        [
                1
                2
                3
        ]
        """
        s = self.clone()
        s._s.rename(name)
        return s

    def rename(self, name: str) -> Series:
        """
        Rename this Series.

        Alias for :func:`Series.alias`.

        Parameters
        ----------
        name
            New name.

        Examples
        --------
        >>> s = pl.Series("a", [1, 2, 3])
        >>> s.rename("b")
        shape: (3,)
        Series: 'b' [i64]
        [
                1
                2
                3
        ]
        """
        return self.alias(name)

    def chunk_lengths(self) -> list[int]:
        """
        Get the length of each individual chunk.

        Examples
        --------
        >>> s = pl.Series("a", [1, 2, 3])
        >>> s2 = pl.Series("a", [4, 5, 6])

        Concatenate Series with rechunk = True

        >>> pl.concat([s, s2]).chunk_lengths()
        [6]

        Concatenate Series with rechunk = False

        >>> pl.concat([s, s2], rechunk=False).chunk_lengths()
        [3, 3]
        """
        return self._s.chunk_lengths()

    def n_chunks(self) -> int:
        """
        Get the number of chunks that this Series contains.

        Examples
        --------
        >>> s = pl.Series("a", [1, 2, 3])
        >>> s.n_chunks()
        1
        >>> s2 = pl.Series("a", [4, 5, 6])

        Concatenate Series with rechunk = True

        >>> pl.concat([s, s2]).n_chunks()
        1

        Concatenate Series with rechunk = False

        >>> pl.concat([s, s2], rechunk=False).n_chunks()
        2
        """
        return self._s.n_chunks()

    def cum_max(self, *, reverse: bool = False) -> Series:
        """
        Get an array with the cumulative max computed at every element.

        Parameters
        ----------
        reverse
            reverse the operation.

        Examples
        --------
        >>> s = pl.Series("s", [3, 5, 1])
        >>> s.cum_max()
        shape: (3,)
        Series: 's' [i64]
        [
            3
            5
            5
        ]
        """

    def cum_min(self, *, reverse: bool = False) -> Series:
        """
        Get an array with the cumulative min computed at every element.

        Parameters
        ----------
        reverse
            reverse the operation.

        Examples
        --------
        >>> s = pl.Series("s", [1, 2, 3])
        >>> s.cum_min()
        shape: (3,)
        Series: 's' [i64]
        [
            1
            1
            1
        ]
        """

    def cum_prod(self, *, reverse: bool = False) -> Series:
        """
        Get an array with the cumulative product computed at every element.

        Parameters
        ----------
        reverse
            reverse the operation.

        Notes
        -----
        Dtypes in {Int8, UInt8, Int16, UInt16} are cast to
        Int64 before summing to prevent overflow issues.

        Examples
        --------
        >>> s = pl.Series("a", [1, 2, 3])
        >>> s.cum_prod()
        shape: (3,)
        Series: 'a' [i64]
        [
            1
            2
            6
        ]
        """

    def cum_sum(self, *, reverse: bool = False) -> Series:
        """
        Get an array with the cumulative sum computed at every element.

        Parameters
        ----------
        reverse
            reverse the operation.

        Notes
        -----
        Dtypes in {Int8, UInt8, Int16, UInt16} are cast to
        Int64 before summing to prevent overflow issues.

        Examples
        --------
        >>> s = pl.Series("a", [1, 2, 3])
        >>> s.cum_sum()
        shape: (3,)
        Series: 'a' [i64]
        [
            1
            3
            6
        ]
        """

    def cum_count(self, *, reverse: bool = False) -> Self:
        """
        Return the cumulative count of the non-null values in the column.

        Parameters
        ----------
        reverse
            Reverse the operation.

        Examples
        --------
        >>> s = pl.Series(["x", "k", None, "d"])
        >>> s.cum_count()
        shape: (4,)
        Series: '' [u32]
        [
                1
                2
                2
                3
        ]
        """

    def slice(self, offset: int, length: int | None = None) -> Series:
        """
        Get a slice of this Series.

        Parameters
        ----------
        offset
            Start index. Negative indexing is supported.
        length
            Length of the slice. If set to `None`, all rows starting at the offset
            will be selected.

        Examples
        --------
        >>> s = pl.Series("a", [1, 2, 3, 4])
        >>> s.slice(1, 2)
        shape: (2,)
        Series: 'a' [i64]
        [
                2
                3
        ]
        """
        return self._from_pyseries(self._s.slice(offset=offset, length=length))

    def append(self, other: Series) -> Self:
        """
        Append a Series to this one.

        The resulting series will consist of multiple chunks.

        Parameters
        ----------
        other
            Series to append.

        Warnings
        --------
        This method modifies the series in-place. The series is returned for
        convenience only.

        See Also
        --------
        extend

        Examples
        --------
        >>> a = pl.Series("a", [1, 2, 3])
        >>> b = pl.Series("b", [4, 5])
        >>> a.append(b)
        shape: (5,)
        Series: 'a' [i64]
        [
            1
            2
            3
            4
            5
        ]

        The resulting series will consist of multiple chunks.

        >>> a.n_chunks()
        2
        """
        try:
            self._s.append(other._s)
        except RuntimeError as exc:
            if str(exc) == "Already mutably borrowed":
                self._s.append(other._s.clone())
            else:
                raise
        return self

    def extend(self, other: Series) -> Self:
        """
        Extend the memory backed by this Series with the values from another.

        Different from `append`, which adds the chunks from `other` to the chunks of
        this series, `extend` appends the data from `other` to the underlying memory
        locations and thus may cause a reallocation (which is expensive).

        If this does `not` cause a reallocation, the resulting data structure will not
        have any extra chunks and thus will yield faster queries.

        Prefer `extend` over `append` when you want to do a query after a single
        append. For instance, during online operations where you add `n` rows
        and rerun a query.

        Prefer `append` over `extend` when you want to append many times
        before doing a query. For instance, when you read in multiple files and want
        to store them in a single `Series`. In the latter case, finish the sequence
        of `append` operations with a `rechunk`.

        Parameters
        ----------
        other
            Series to extend the series with.

        Warnings
        --------
        This method modifies the series in-place. The series is returned for
        convenience only.

        See Also
        --------
        append

        Examples
        --------
        >>> a = pl.Series("a", [1, 2, 3])
        >>> b = pl.Series("b", [4, 5])
        >>> a.extend(b)
        shape: (5,)
        Series: 'a' [i64]
        [
            1
            2
            3
            4
            5
        ]

        The resulting series will consist of a single chunk.

        >>> a.n_chunks()
        1
        """
        try:
            self._s.extend(other._s)
        except RuntimeError as exc:
            if str(exc) == "Already mutably borrowed":
                self._s.extend(other._s.clone())
            else:
                raise
        return self

    def filter(self, predicate: Series | list[bool]) -> Self:
        """
        Filter elements by a boolean mask.

        The original order of the remaining elements is preserved.

        Parameters
        ----------
        predicate
            Boolean mask.

        Examples
        --------
        >>> s = pl.Series("a", [1, 2, 3])
        >>> mask = pl.Series("", [True, False, True])
        >>> s.filter(mask)
        shape: (2,)
        Series: 'a' [i64]
        [
                1
                3
        ]
        """
        if isinstance(predicate, list):
            predicate = Series("", predicate)
        return self._from_pyseries(self._s.filter(predicate._s))

    def head(self, n: int = 10) -> Series:
        """
        Get the first `n` elements.

        Parameters
        ----------
        n
            Number of elements to return. If a negative value is passed, return all
            elements except the last `abs(n)`.

        See Also
        --------
        tail, slice

        Examples
        --------
        >>> s = pl.Series("a", [1, 2, 3, 4, 5])
        >>> s.head(3)
        shape: (3,)
        Series: 'a' [i64]
        [
                1
                2
                3
        ]

        Pass a negative value to get all rows `except` the last `abs(n)`.

        >>> s.head(-3)
        shape: (2,)
        Series: 'a' [i64]
        [
                1
                2
        ]
        """
        if n < 0:
            n = max(0, self.len() + n)
        return self._from_pyseries(self._s.head(n))

    def tail(self, n: int = 10) -> Series:
        """
        Get the last `n` elements.

        Parameters
        ----------
        n
            Number of elements to return. If a negative value is passed, return all
            elements except the first `abs(n)`.

        See Also
        --------
        head, slice

        Examples
        --------
        >>> s = pl.Series("a", [1, 2, 3, 4, 5])
        >>> s.tail(3)
        shape: (3,)
        Series: 'a' [i64]
        [
                3
                4
                5
        ]

        Pass a negative value to get all rows `except` the first `abs(n)`.

        >>> s.tail(-3)
        shape: (2,)
        Series: 'a' [i64]
        [
                4
                5
        ]
        """
        if n < 0:
            n = max(0, self.len() + n)
        return self._from_pyseries(self._s.tail(n))

    def limit(self, n: int = 10) -> Series:
        """
        Get the first `n` elements.

        Alias for :func:`Series.head`.

        Parameters
        ----------
        n
            Number of elements to return. If a negative value is passed, return all
            elements except the last `abs(n)`.

        See Also
        --------
        head
        
        Examples
        --------
        >>> s = pl.Series("a", [1, 2, 3, 4, 5])
        >>> s.limit(3)
        shape: (3,)
        Series: 'a' [i64]
        [
            1
            2
            3
        ]
        
        Pass a negative value to get all rows `except` the last `abs(n)`.
        
        >>> s.limit(-3)
        shape: (2,)
        Series: 'a' [i64]
        [
                1
                2
        ]
        """
        return self.head(n)

    def gather_every(self, n: int, offset: int = 0) -> Series:
        """
        Take every nth value in the Series and return as new Series.

        Parameters
        ----------
        n
            Gather every *n*-th row.
        offset
            Start the row index at this offset.

        Examples
        --------
        >>> s = pl.Series("a", [1, 2, 3, 4])
        >>> s.gather_every(2)
        shape: (2,)
        Series: 'a' [i64]
        [
            1
            3
        ]
        >>> s.gather_every(2, offset=1)
        shape: (2,)
        Series: 'a' [i64]
        [
            2
            4
        ]
        """

    def sort(
        self,
        *,
        descending: bool = False,
        nulls_last: bool = False,
        multithreaded: bool = True,
        in_place: bool = False,
    ) -> Self:
        """
        Sort this Series.

        Parameters
        ----------
        descending
            Sort in descending order.
        nulls_last
            Place null values last instead of first.
        multithreaded
            Sort using multiple threads.
        in_place
            Sort in-place.

        Examples
        --------
        >>> s = pl.Series("a", [1, 3, 4, 2])
        >>> s.sort()
        shape: (4,)
        Series: 'a' [i64]
        [
                1
                2
                3
                4
        ]
        >>> s.sort(descending=True)
        shape: (4,)
        Series: 'a' [i64]
        [
                4
                3
                2
                1
        ]
        """
        if in_place:
            self._s = self._s.sort(descending, nulls_last, multithreaded)
            return self
        else:
            return self._from_pyseries(
                self._s.sort(descending, nulls_last, multithreaded)
            )

    def top_k(self, k: int | IntoExprColumn = 5) -> Series:
        r"""
        Return the `k` largest elements.

        This has time complexity:

        .. math:: O(n + k \log{n} - \frac{k}{2})

        Parameters
        ----------
        k
            Number of elements to return.

        See Also
        --------
        bottom_k

        Examples
        --------
        >>> s = pl.Series("a", [2, 5, 1, 4, 3])
        >>> s.top_k(3)
        shape: (3,)
        Series: 'a' [i64]
        [
            5
            4
            3
        ]
        """

    def bottom_k(self, k: int | IntoExprColumn = 5) -> Series:
        r"""
        Return the `k` smallest elements.

        This has time complexity:

        .. math:: O(n + k \log{n} - \frac{k}{2})

        Parameters
        ----------
        k
            Number of elements to return.

        See Also
        --------
        top_k

        Examples
        --------
        >>> s = pl.Series("a", [2, 5, 1, 4, 3])
        >>> s.bottom_k(3)
        shape: (3,)
        Series: 'a' [i64]
        [
            1
            2
            3
        ]
        """

    def arg_sort(self, *, descending: bool = False, nulls_last: bool = False) -> Series:
        """
        Get the index values that would sort this Series.

        Parameters
        ----------
        descending
            Sort in descending order.
        nulls_last
            Place null values last instead of first.

        See Also
        --------
        Series.gather: Take values by index.
        Series.rank : Get the rank of each row.

        Examples
        --------
        >>> s = pl.Series("a", [5, 3, 4, 1, 2])
        >>> s.arg_sort()
        shape: (5,)
        Series: 'a' [u32]
        [
            3
            4
            1
            2
            0
        ]
        """

    def arg_unique(self) -> Series:
        """
        Get unique index as Series.

        Returns
        -------
        Series

        Examples
        --------
        >>> s = pl.Series("a", [1, 2, 2, 3])
        >>> s.arg_unique()
        shape: (3,)
        Series: 'a' [u32]
        [
                0
                1
                3
        ]
        """

    def arg_min(self) -> int | None:
        """
        Get the index of the minimal value.

        Returns
        -------
        int

        Examples
        --------
        >>> s = pl.Series("a", [3, 2, 1])
        >>> s.arg_min()
        2
        """
        return self._s.arg_min()

    def arg_max(self) -> int | None:
        """
        Get the index of the maximal value.

        Returns
        -------
        int

        Examples
        --------
        >>> s = pl.Series("a", [3, 2, 1])
        >>> s.arg_max()
        0
        """
        return self._s.arg_max()

    @overload
    def search_sorted(
        self, element: NonNestedLiteral, side: SearchSortedSide = ...
    ) -> int: ...

    @overload
    def search_sorted(
        self,
        element: list[NonNestedLiteral] | np.ndarray[Any, Any] | Expr | Series,
        side: SearchSortedSide = ...,
    ) -> Series: ...

    def search_sorted(
        self,
        element: IntoExpr | np.ndarray[Any, Any],
        side: SearchSortedSide = "any",
    ) -> int | Series:
        """
        Find indices where elements should be inserted to maintain order.

        .. math:: a[i-1] < v <= a[i]

        Parameters
        ----------
        element
            Expression or scalar value.
        side : {'any', 'left', 'right'}
            If 'any', the index of the first suitable location found is given.
            If 'left', the index of the leftmost suitable location found is given.
            If 'right', return the rightmost suitable location found is given.

        Examples
        --------
        >>> s = pl.Series("set", [1, 2, 3, 4, 4, 5, 6, 7])
        >>> s.search_sorted(4)
        4
        >>> s.search_sorted(4, "left")
        3
        >>> s.search_sorted(4, "right")
        5
        >>> s.search_sorted([1, 4, 5])
        shape: (3,)
        Series: 'set' [u32]
        [
                0
                4
                5
        ]
        >>> s.search_sorted([1, 4, 5], "left")
        shape: (3,)
        Series: 'set' [u32]
        [
                0
                3
                5
        ]
        >>> s.search_sorted([1, 4, 5], "right")
        shape: (3,)
        Series: 'set' [u32]
        [
                1
                5
                6
        ]
        """
        df = F.select(F.lit(self).search_sorted(element, side))
        if isinstance(element, (list, Series, pl.Expr, np.ndarray)):
            return df.to_series()
        else:
            return df.item()

    def unique(self, *, maintain_order: bool = False) -> Series:
        """
        Get unique elements in series.

        Parameters
        ----------
        maintain_order
            Maintain order of data. This requires more work.

        Examples
        --------
        >>> s = pl.Series("a", [1, 2, 2, 3])
        >>> s.unique().sort()
        shape: (3,)
        Series: 'a' [i64]
        [
            1
            2
            3
        ]
        """

    def gather(
        self, indices: int | list[int] | Expr | Series | np.ndarray[Any, Any]
    ) -> Series:
        """
        Take values by index.

        Parameters
        ----------
        indices
            Index location used for selection.

        Examples
        --------
        >>> s = pl.Series("a", [1, 2, 3, 4])
        >>> s.gather([1, 3])
        shape: (2,)
        Series: 'a' [i64]
        [
                2
                4
        ]
        """

    def null_count(self) -> int:
        """
        Count the null values in this Series.

        Examples
        --------
        >>> s = pl.Series([1, None, None])
        >>> s.null_count()
        2
        """
        return self._s.null_count()

    def has_validity(self) -> bool:
        """
        Return True if the Series has a validity bitmask.

        If there is no mask, it means that there are no `null` values.

        Notes
        -----
        While the *absence* of a validity bitmask guarantees that a Series does not
        have `null` values, the converse is not true, eg: the *presence* of a
        bitmask does not mean that there are null values, as every value of the
        bitmask could be `false`.

        To confirm that a column has `null` values use :func:`null_count`.
        """
        return self._s.has_validity()

    def is_empty(self) -> bool:
        """
        Check if the Series is empty.

        Examples
        --------
        >>> s = pl.Series("a", [], dtype=pl.Float32)
        >>> s.is_empty()
        True
        """
        return self.len() == 0

    def is_sorted(self, *, descending: bool = False) -> bool:
        """
        Check if the Series is sorted.

        Parameters
        ----------
        descending
            Check if the Series is sorted in descending order

        Examples
        --------
        >>> s = pl.Series([1, 3, 2])
        >>> s.is_sorted()
        False

        >>> s = pl.Series([3, 2, 1])
        >>> s.is_sorted(descending=True)
        True
        """
        return self._s.is_sorted(descending)

    def not_(self) -> Series:
        """
        Negate a boolean Series.

        Returns
        -------
        Series
            Series of data type :class:`Boolean`.

        Examples
        --------
        >>> s = pl.Series("a", [True, False, False])
        >>> s.not_()
        shape: (3,)
        Series: 'a' [bool]
        [
            false
            true
            true
        ]
        """
        return self._from_pyseries(self._s.not_())

    def is_null(self) -> Series:
        """
        Returns a boolean Series indicating which values are null.

        Returns
        -------
        Series
            Series of data type :class:`Boolean`.

        Examples
        --------
        >>> s = pl.Series("a", [1.0, 2.0, 3.0, None])
        >>> s.is_null()
        shape: (4,)
        Series: 'a' [bool]
        [
            false
            false
            false
            true
        ]
        """

    def is_not_null(self) -> Series:
        """
        Returns a boolean Series indicating which values are not null.

        Returns
        -------
        Series
            Series of data type :class:`Boolean`.

        Examples
        --------
        >>> s = pl.Series("a", [1.0, 2.0, 3.0, None])
        >>> s.is_not_null()
        shape: (4,)
        Series: 'a' [bool]
        [
            true
            true
            true
            false
        ]
        """

    def is_finite(self) -> Series:
        """
        Returns a boolean Series indicating which values are finite.

        Returns
        -------
        Series
            Series of data type :class:`Boolean`.

        Examples
        --------
        >>> import numpy as np
        >>> s = pl.Series("a", [1.0, 2.0, np.inf])
        >>> s.is_finite()
        shape: (3,)
        Series: 'a' [bool]
        [
                true
                true
                false
        ]
        """

    def is_infinite(self) -> Series:
        """
        Returns a boolean Series indicating which values are infinite.

        Returns
        -------
        Series
            Series of data type :class:`Boolean`.

        Examples
        --------
        >>> import numpy as np
        >>> s = pl.Series("a", [1.0, 2.0, np.inf])
        >>> s.is_infinite()
        shape: (3,)
        Series: 'a' [bool]
        [
                false
                false
                true
        ]
        """

    def is_nan(self) -> Series:
        """
        Returns a boolean Series indicating which values are not NaN.

        Returns
        -------
        Series
            Series of data type :class:`Boolean`.

        Examples
        --------
        >>> import numpy as np
        >>> s = pl.Series("a", [1.0, 2.0, 3.0, np.nan])
        >>> s.is_nan()
        shape: (4,)
        Series: 'a' [bool]
        [
                false
                false
                false
                true
        ]
        """

    def is_not_nan(self) -> Series:
        """
        Returns a boolean Series indicating which values are not NaN.

        Returns
        -------
        Series
            Series of data type :class:`Boolean`.

        Examples
        --------
        >>> import numpy as np
        >>> s = pl.Series("a", [1.0, 2.0, 3.0, np.nan])
        >>> s.is_not_nan()
        shape: (4,)
        Series: 'a' [bool]
        [
                true
                true
                true
                false
        ]
        """

    def is_in(self, other: Series | Collection[Any]) -> Series:
        """
        Check if elements of this Series are in the other Series.

        Returns
        -------
        Series
            Series of data type :class:`Boolean`.

        Examples
        --------
        >>> s = pl.Series("a", [1, 2, 3])
        >>> s2 = pl.Series("b", [2, 4])
        >>> s2.is_in(s)
        shape: (2,)
        Series: 'b' [bool]
        [
                true
                false
        ]

        >>> # check if some values are a member of sublists
        >>> sets = pl.Series("sets", [[1, 2, 3], [1, 2], [9, 10]])
        >>> optional_members = pl.Series("optional_members", [1, 2, 3])
        >>> print(sets)
        shape: (3,)
        Series: 'sets' [list[i64]]
        [
            [1, 2, 3]
            [1, 2]
            [9, 10]
        ]
        >>> print(optional_members)
        shape: (3,)
        Series: 'optional_members' [i64]
        [
            1
            2
            3
        ]
        >>> optional_members.is_in(sets)
        shape: (3,)
        Series: 'optional_members' [bool]
        [
            true
            true
            false
        ]
        """

    def arg_true(self) -> Series:
        """
        Get index values where Boolean Series evaluate True.

        Returns
        -------
        Series
            Series of data type :class:`UInt32`.

        Examples
        --------
        >>> s = pl.Series("a", [1, 2, 3])
        >>> (s == 2).arg_true()
        shape: (1,)
        Series: 'a' [u32]
        [
                1
        ]
        """
        return F.arg_where(self, eager=True)

    def is_unique(self) -> Series:
        """
        Get mask of all unique values.

        Returns
        -------
        Series
            Series of data type :class:`Boolean`.

        Examples
        --------
        >>> s = pl.Series("a", [1, 2, 2, 3])
        >>> s.is_unique()
        shape: (4,)
        Series: 'a' [bool]
        [
                true
                false
                false
                true
        ]
        """

    def is_first_distinct(self) -> Series:
        """
        Return a boolean mask indicating the first occurrence of each distinct value.

        Returns
        -------
        Series
            Series of data type :class:`Boolean`.

        Examples
        --------
        >>> s = pl.Series([1, 1, 2, 3, 2])
        >>> s.is_first_distinct()
        shape: (5,)
        Series: '' [bool]
        [
                true
                false
                true
                true
                false
        ]
        """

    def is_last_distinct(self) -> Series:
        """
        Return a boolean mask indicating the last occurrence of each distinct value.

        Returns
        -------
        Series
            Series of data type :class:`Boolean`.

        Examples
        --------
        >>> s = pl.Series([1, 1, 2, 3, 2])
        >>> s.is_last_distinct()
        shape: (5,)
        Series: '' [bool]
        [
                false
                true
                false
                true
                true
        ]
        """

    def is_duplicated(self) -> Series:
        """
        Get mask of all duplicated values.

        Returns
        -------
        Series
            Series of data type :class:`Boolean`.

        Examples
        --------
        >>> s = pl.Series("a", [1, 2, 2, 3])
        >>> s.is_duplicated()
        shape: (4,)
        Series: 'a' [bool]
        [
                false
                true
                true
                false
        ]
        """

    def explode(self) -> Series:
        """
        Explode a list Series.

        This means that every item is expanded to a new row.

        Returns
        -------
        Series
            Series with the data type of the list elements.

        See Also
        --------
        Series.list.explode : Explode a list column.
        Series.str.explode : Explode a string column.

        Examples
        --------
        >>> s = pl.Series("a", [[1, 2, 3], [4,5,6]])
        >>> s
        shape: (2,)
        Series: 'a' [list[i64]]
        [
                [1, 2, 3]
                [4, 5, 6]
        ]
        >>> s.explode()
        shape: (6,)
        Series: 'a' [i64]
        [
                1
                2
                3
                4
                5
                6
        ]
        """

    def equals(
        self, other: Series, *, null_equal: bool = True, strict: bool = False
    ) -> bool:
        """
        Check whether the Series is equal to another Series.

        Parameters
        ----------
        other
            Series to compare with.
        null_equal
            Consider null values as equal.
        strict
            Don't allow different numerical dtypes, e.g. comparing `pl.UInt32` with a
            `pl.Int64` will return `False`.

        See Also
        --------
        assert_series_equal

        Examples
        --------
        >>> s1 = pl.Series("a", [1, 2, 3])
        >>> s2 = pl.Series("b", [4, 5, 6])
        >>> s1.equals(s1)
        True
        >>> s1.equals(s2)
        False
        """
        return self._s.equals(other._s, null_equal, strict)

    def cast(
        self,
        dtype: (PolarsDataType | type[int] | type[float] | type[str] | type[bool]),
        *,
        strict: bool = True,
    ) -> Self:
        """
        Cast between data types.

        Parameters
        ----------
        dtype
            DataType to cast to.
        strict
            Throw an error if a cast could not be done (for instance, due to an
            overflow).

        Examples
        --------
        >>> s = pl.Series("a", [True, False, True])
        >>> s
        shape: (3,)
        Series: 'a' [bool]
        [
            true
            false
            true
        ]

        >>> s.cast(pl.UInt32)
        shape: (3,)
        Series: 'a' [u32]
        [
            1
            0
            1
        ]
        """
        # Do not dispatch cast as it is expensive and used in other functions.
        dtype = py_type_to_dtype(dtype)
        return self._from_pyseries(self._s.cast(dtype, strict))

    def to_physical(self) -> Series:
        """
        Cast to physical representation of the logical dtype.

        - :func:`polars.datatypes.Date` -> :func:`polars.datatypes.Int32`
        - :func:`polars.datatypes.Datetime` -> :func:`polars.datatypes.Int64`
        - :func:`polars.datatypes.Time` -> :func:`polars.datatypes.Int64`
        - :func:`polars.datatypes.Duration` -> :func:`polars.datatypes.Int64`
        - :func:`polars.datatypes.Categorical` -> :func:`polars.datatypes.UInt32`
        - `List(inner)` -> `List(physical of inner)`
        - Other data types will be left unchanged.

        Examples
        --------
        Replicating the pandas
        `pd.Series.factorize
        <https://pandas.pydata.org/docs/reference/api/pandas.Series.factorize.html>`_
        method.

        >>> s = pl.Series("values", ["a", None, "x", "a"])
        >>> s.cast(pl.Categorical).to_physical()
        shape: (4,)
        Series: 'values' [u32]
        [
            0
            null
            1
            0
        ]
        """

    def to_list(self, *, use_pyarrow: bool | None = None) -> list[Any]:
        """
        Convert this Series to a Python list.

        This operation copies data.

        Parameters
        ----------
        use_pyarrow
            Use PyArrow to perform the conversion.

            .. deprecated:: 0.19.9
                This parameter will be removed. The function can safely be called
                without the parameter - it should give the exact same result.

        Examples
        --------
        >>> s = pl.Series("a", [1, 2, 3])
        >>> s.to_list()
        [1, 2, 3]
        >>> type(s.to_list())
        <class 'list'>
        """
        if use_pyarrow is not None:
            issue_deprecation_warning(
                "The parameter `use_pyarrow` for `Series.to_list` is deprecated."
                " Call the method without `use_pyarrow` to silence this warning.",
                version="0.19.9",
            )
            if use_pyarrow:
                return self.to_arrow().to_pylist()

        return self._s.to_list()

    def rechunk(self, *, in_place: bool = False) -> Self:
        """
        Create a single chunk of memory for this Series.

        Parameters
        ----------
        in_place
            In place or not.

        Examples
        --------
        >>> s1 = pl.Series("a", [1, 2, 3])
        >>> s1.n_chunks()
        1
        >>> s2 = pl.Series("a", [4, 5, 6])
        >>> s = pl.concat([s1, s2], rechunk=False)
        >>> s.n_chunks()
        2
        >>> s.rechunk(in_place=True)
        shape: (6,)
        Series: 'a' [i64]
        [
                1
                2
                3
                4
                5
                6
        ]
        >>> s.n_chunks()
        1
        """
        opt_s = self._s.rechunk(in_place)
        return self if in_place else self._from_pyseries(opt_s)

    def reverse(self) -> Series:
        """
        Return Series in reverse order.

        Examples
        --------
        >>> s = pl.Series("a", [1, 2, 3], dtype=pl.Int8)
        >>> s.reverse()
        shape: (3,)
        Series: 'a' [i8]
        [
            3
            2
            1
        ]
        """

    def is_between(
        self,
        lower_bound: IntoExpr,
        upper_bound: IntoExpr,
        closed: ClosedInterval = "both",
    ) -> Series:
        """
        Get a boolean mask of the values that are between the given lower/upper bounds.

        Parameters
        ----------
        lower_bound
            Lower bound value. Accepts expression input. Non-expression inputs
            (including strings) are parsed as literals.
        upper_bound
            Upper bound value. Accepts expression input. Non-expression inputs
            (including strings) are parsed as literals.
        closed : {'both', 'left', 'right', 'none'}
            Define which sides of the interval are closed (inclusive).

        Notes
        -----
        If the value of the `lower_bound` is greater than that of the `upper_bound`
        then the result will be False, as no value can satisfy the condition.

        Examples
        --------
        >>> s = pl.Series("num", [1, 2, 3, 4, 5])
        >>> s.is_between(2, 4)
        shape: (5,)
        Series: 'num' [bool]
        [
            false
            true
            true
            true
            false
        ]

        Use the `closed` argument to include or exclude the values at the bounds:

        >>> s.is_between(2, 4, closed="left")
        shape: (5,)
        Series: 'num' [bool]
        [
            false
            true
            true
            false
            false
        ]

        You can also use strings as well as numeric/temporal values:

        >>> s = pl.Series("s", ["a", "b", "c", "d", "e"])
        >>> s.is_between("b", "d", closed="both")
        shape: (5,)
        Series: 's' [bool]
        [
            false
            true
            true
            true
            false
        ]
        """
        if closed == "none":
            out = (self > lower_bound) & (self < upper_bound)
        elif closed == "both":
            out = (self >= lower_bound) & (self <= upper_bound)
        elif closed == "right":
            out = (self > lower_bound) & (self <= upper_bound)
        elif closed == "left":
            out = (self >= lower_bound) & (self < upper_bound)

        if isinstance(out, pl.Expr):
            out = F.select(out).to_series()

        return out

    def to_numpy(
        self,
        *,
        allow_copy: bool = True,
        writable: bool = False,
        use_pyarrow: bool = True,
        zero_copy_only: bool | None = None,
    ) -> np.ndarray[Any, Any]:
        """
        Convert this Series to a NumPy ndarray.

        This operation may copy data, but is completely safe. Note that:

        - Data which is purely numeric AND without null values is not cloned
        - Floating point `nan` values can be zero-copied
        - Booleans cannot be zero-copied

        To ensure that no data is copied, set `allow_copy=False`.

        Parameters
        ----------
        allow_copy
            Allow memory to be copied to perform the conversion. If set to `False`,
            causes conversions that are not zero-copy to fail.
        writable
            Ensure the resulting array is writable. This will force a copy of the data
            if the array was created without copy, as the underlying Arrow data is
            immutable.
        use_pyarrow
            Use `pyarrow.Array.to_numpy
            <https://arrow.apache.org/docs/python/generated/pyarrow.Array.html#pyarrow.Array.to_numpy>`_
            for the conversion to NumPy.
        zero_copy_only
            Raise an exception if the conversion to a NumPy would require copying
            the underlying data. Data copy occurs, for example, when the Series contains
            nulls or non-numeric types.

            .. deprecated:: 0.20.10
                Use the `allow_copy` parameter instead, which is the inverse of this
                one.

        Examples
        --------
        >>> s = pl.Series("a", [1, 2, 3])
        >>> arr = s.to_numpy()
        >>> arr  # doctest: +IGNORE_RESULT
        array([1, 2, 3], dtype=int64)
        >>> type(arr)
        <class 'numpy.ndarray'>
        """
        if zero_copy_only is not None:
            issue_deprecation_warning(
                "The `zero_copy_only` parameter for `Series.to_numpy` is deprecated."
                " Use the `allow_copy` parameter instead, which is the inverse of `zero_copy_only`.",
                version="0.20.10",
            )
            allow_copy = not zero_copy_only

        def raise_on_copy() -> None:
            if not allow_copy and not self.is_empty():
                msg = "cannot return a zero-copy array"
                raise ValueError(msg)

        def temporal_dtype_to_numpy(dtype: PolarsDataType) -> Any:
            if dtype == Date:
                return np.dtype("datetime64[D]")
            elif dtype == Duration:
                return np.dtype(f"timedelta64[{dtype.time_unit}]")  # type: ignore[union-attr]
            elif dtype == Datetime:
                return np.dtype(f"datetime64[{dtype.time_unit}]")  # type: ignore[union-attr]
            else:
                msg = f"invalid temporal type: {dtype}"
                raise TypeError(msg)

        if self.n_chunks() > 1:
            raise_on_copy()
            self = self.rechunk()

        dtype = self.dtype

        if dtype == Array:
            np_array = self.explode().to_numpy(
                allow_copy=allow_copy,
                writable=writable,
                use_pyarrow=use_pyarrow,
            )
            np_array.shape = (self.len(), self.dtype.width)  # type: ignore[attr-defined]
            return np_array

        if (
            use_pyarrow
            and _PYARROW_AVAILABLE
            and dtype not in (Object, Datetime, Duration, Date)
        ):
            return self.to_arrow().to_numpy(
                zero_copy_only=not allow_copy, writable=writable
            )

        if self.null_count() == 0:
            if dtype.is_integer() or dtype.is_float():
                np_array = self._s.to_numpy_view()
            elif dtype == Boolean:
                raise_on_copy()
                s_u8 = self.cast(UInt8)
                np_array = s_u8._s.to_numpy_view().view(bool)
            elif dtype in (Datetime, Duration):
                np_dtype = temporal_dtype_to_numpy(dtype)
                s_i64 = self.to_physical()
                np_array = s_i64._s.to_numpy_view().view(np_dtype)
            elif dtype == Date:
                raise_on_copy()
                np_dtype = temporal_dtype_to_numpy(dtype)
                s_i32 = self.to_physical()
                np_array = s_i32._s.to_numpy_view().astype(np_dtype)
            else:
                raise_on_copy()
                np_array = self._s.to_numpy()

        else:
            raise_on_copy()
            np_array = self._s.to_numpy()
            if dtype in (Datetime, Duration, Date):
                np_dtype = temporal_dtype_to_numpy(dtype)
                np_array = np_array.view(np_dtype)

        if writable and not np_array.flags.writeable:
            raise_on_copy()
            np_array = np_array.copy()

        return np_array

    def to_torch(self) -> torch.Tensor:
        """
        Convert this Series to a PyTorch tensor.

        Examples
        --------
        >>> s = pl.Series("x", [1, 0, 1, 2, 0], dtype=pl.UInt8)
        >>> s.to_torch()
        tensor([1, 0, 1, 2, 0], dtype=torch.uint8)
        """
        torch = import_optional("torch")

        # PyTorch tensors do not support uint16/32/64
        if self.dtype in (UInt32, UInt64):
            srs = self.cast(Int64)
        elif self.dtype == UInt16:
            srs = self.cast(Int32)
        else:
            srs = self

        # we have to build the tensor from a writable array or PyTorch will complain
        # about it (as writing to readonly array results in undefined behavior)
        numpy_array = srs.to_numpy(writable=True, use_pyarrow=False)
        tensor = torch.from_numpy(numpy_array)

        # note: named tensors are currently experimental
        # tensor.rename(self.name)
        return tensor

    def to_arrow(self) -> pa.Array:
        """
        Return the underlying Arrow array.

        If the Series contains only a single chunk this operation is zero copy.

        Examples
        --------
        >>> s = pl.Series("a", [1, 2, 3])
        >>> s = s.to_arrow()
        >>> s  # doctest: +ELLIPSIS
        <pyarrow.lib.Int64Array object at ...>
        [
          1,
          2,
          3
        ]
        """
        return self._s.to_arrow()

    def to_pandas(
        self, *, use_pyarrow_extension_array: bool = False, **kwargs: Any
    ) -> pd.Series[Any]:
        """
        Convert this Series to a pandas Series.

        This operation copies data if `use_pyarrow_extension_array` is not enabled.

        Parameters
        ----------
        use_pyarrow_extension_array
            Use a PyArrow-backed extension array instead of a NumPy array for the pandas
            Series. This allows zero copy operations and preservation of null values.
            Subsequent operations on the resulting pandas Series may trigger conversion
            to NumPy if those operations are not supported by PyArrow compute functions.
        **kwargs
            Additional keyword arguments to be passed to
            :meth:`pyarrow.Array.to_pandas`.

        Returns
        -------
        :class:`pandas.Series`

        Notes
        -----
        This operation requires that both :mod:`pandas` and :mod:`pyarrow` are
        installed.

        Examples
        --------
        >>> s = pl.Series("a", [1, 2, 3])
        >>> s.to_pandas()
        0    1
        1    2
        2    3
        Name: a, dtype: int64

        Null values are converted to `NaN`.

        >>> s = pl.Series("b", [1, 2, None])
        >>> s.to_pandas()
        0    1.0
        1    2.0
        2    NaN
        Name: b, dtype: float64

        Pass `use_pyarrow_extension_array=True` to get a pandas Series backed by a
        PyArrow extension array. This will preserve null values.

        >>> s.to_pandas(use_pyarrow_extension_array=True)
        0       1
        1       2
        2    <NA>
        Name: b, dtype: int64[pyarrow]
        """
        if self.dtype == Object:
            # Can't convert via PyArrow, so do it via NumPy
            return pd.Series(self.to_numpy(), dtype=object, name=self.name)

        if use_pyarrow_extension_array:
            if parse_version(pd.__version__) < (1, 5):
                msg = f'pandas>=1.5.0 is required for `to_pandas("use_pyarrow_extension_array=True")`, found Pandas {pd.__version__}'
                raise ModuleUpgradeRequired(msg)
            if not _PYARROW_AVAILABLE or parse_version(pa.__version__) < (8, 0):
                raise ModuleUpgradeRequired(
                    f'pyarrow>=8.0.0 is required for `to_pandas("use_pyarrow_extension_array=True")`'
                    f", found pyarrow {pa.__version__!r}"
                    if _PYARROW_AVAILABLE
                    else ""
                )

        pa_arr = self.to_arrow()
        # pandas does not support unsigned dictionary indices
        if pa.types.is_dictionary(pa_arr.type):
            pa_arr = pa_arr.cast(pa.dictionary(pa.int64(), pa.large_string()))

        if use_pyarrow_extension_array:
            pd_series = pa_arr.to_pandas(
                self_destruct=True,
                split_blocks=True,
                types_mapper=lambda pa_dtype: pd.ArrowDtype(pa_dtype),
                **kwargs,
            )
        else:
            date_as_object = kwargs.pop("date_as_object", False)
            pd_series = pa_arr.to_pandas(date_as_object=date_as_object, **kwargs)

        pd_series.name = self.name
        return pd_series

    def to_init_repr(self, n: int = 1000) -> str:
        """
        Convert Series to instantiatable string representation.

        Parameters
        ----------
        n
            Only use first n elements.

        See Also
        --------
        polars.Series.to_init_repr
        polars.from_repr

        Examples
        --------
        >>> s = pl.Series("a", [1, 2, None, 4], dtype=pl.Int16)
        >>> print(s.to_init_repr())
        pl.Series("a", [1, 2, None, 4], dtype=pl.Int16)
        >>> s_from_str_repr = eval(s.to_init_repr())
        >>> s_from_str_repr
        shape: (4,)
        Series: 'a' [i16]
        [
            1
            2
            null
            4
        ]
        """
        return (
            f'pl.Series("{self.name}", {self.head(n).to_list()}, dtype=pl.{self.dtype})'
        )

    def count(self) -> int:
        """
        Return the number of non-null elements in the column.

        See Also
        --------
        len

        Examples
        --------
        >>> s = pl.Series("a", [1, 2, None])
        >>> s.count()
        2
        """
        return self.len() - self.null_count()

    def len(self) -> int:
        """
        Return the number of elements in the Series.

        Null values count towards the total.

        See Also
        --------
        count

        Examples
        --------
        >>> s = pl.Series("a", [1, 2, None])
        >>> s.len()
        3
        """
        return self._s.len()

    def set(self, filter: Series, value: int | float | str | bool | None) -> Series:
        """
        Set masked values.

        Parameters
        ----------
        filter
            Boolean mask.
        value
            Value with which to replace the masked values.

        Notes
        -----
        Use of this function is frequently an anti-pattern, as it can
        block optimisation (predicate pushdown, etc). Consider using
        `pl.when(predicate).then(value).otherwise(self)` instead.

        Examples
        --------
        >>> s = pl.Series("a", [1, 2, 3])
        >>> s.set(s == 2, 10)
        shape: (3,)
        Series: 'a' [i64]
        [
                1
                10
                3
        ]

        It is better to implement this as follows:

        >>> s.to_frame().select(
        ...     pl.when(pl.col("a") == 2).then(10).otherwise(pl.col("a"))
        ... )
        shape: (3, 1)
        ┌─────────┐
        │ literal │
        │ ---     │
        │ i64     │
        ╞═════════╡
        │ 1       │
        │ 10      │
        │ 3       │
        └─────────┘
        """
        f = get_ffi_func("set_with_mask_<>", self.dtype, self._s)
        if f is None:
            return NotImplemented
        return self._from_pyseries(f(filter._s, value))

    def scatter(
        self,
        indices: Series | Iterable[int] | int | np.ndarray[Any, Any],
        values: Series | Iterable[PythonLiteral] | PythonLiteral | None,
    ) -> Series:
        """
        Set values at the index locations.

        Parameters
        ----------
        indices
            Integers representing the index locations.
        values
            Replacement values.

        Notes
        -----
        Use of this function is frequently an anti-pattern, as it can
        block optimization (predicate pushdown, etc). Consider using
        `pl.when(predicate).then(value).otherwise(self)` instead.

        Examples
        --------
        >>> s = pl.Series("a", [1, 2, 3])
        >>> s.scatter(1, 10)
        shape: (3,)
        Series: 'a' [i64]
        [
                1
                10
                3
        ]

        It is better to implement this as follows:

        >>> s.to_frame().with_row_index().select(
        ...     pl.when(pl.col("index") == 1).then(10).otherwise(pl.col("a"))
        ... )
        shape: (3, 1)
        ┌─────────┐
        │ literal │
        │ ---     │
        │ i64     │
        ╞═════════╡
        │ 1       │
        │ 10      │
        │ 3       │
        └─────────┘
        """
        if not isinstance(indices, Iterable):
            indices = [indices]  # type: ignore[list-item]
        indices = Series(values=indices)
        if indices.is_empty():
            return self

        if not isinstance(values, Series):
            if not isinstance(values, Iterable) or isinstance(values, str):
                values = [values]
            values = Series(values=values)

        self._s.scatter(indices._s, values._s)
        return self

    def clear(self, n: int = 0) -> Series:
        """
        Create an empty copy of the current Series, with zero to 'n' elements.

        The copy has an identical name/dtype, but no data.

        Parameters
        ----------
        n
            Number of (empty) elements to return in the cleared frame.

        See Also
        --------
        clone : Cheap deepcopy/clone.

        Examples
        --------
        >>> s = pl.Series("a", [None, True, False])
        >>> s.clear()
        shape: (0,)
        Series: 'a' [bool]
        [
        ]

        >>> s.clear(n=2)
        shape: (2,)
        Series: 'a' [bool]
        [
            null
            null
        ]
        """
        if n < 0:
            msg = f"`n` should be greater than or equal to 0, got {n}"
            raise ValueError(msg)
        # faster path
        if n == 0:
            return self._from_pyseries(self._s.clear())
        s = (
            self.__class__(name=self.name, values=[], dtype=self.dtype)
            if len(self) > 0
            else self.clone()
        )
        return s.extend_constant(None, n=n) if n > 0 else s

    def clone(self) -> Self:
        """
        Create a copy of this Series.

        This is a cheap operation that does not copy data.

        See Also
        --------
        clear : Create an empty copy of the current Series, with identical
            schema but no data.

        Examples
        --------
        >>> s = pl.Series("a", [1, 2, 3])
        >>> s.clone()
        shape: (3,)
        Series: 'a' [i64]
        [
                1
                2
                3
        ]
        """
        return self._from_pyseries(self._s.clone())

    def fill_nan(self, value: int | float | Expr | None) -> Series:
        """
        Fill floating point NaN value with a fill value.

        Parameters
        ----------
        value
            Value used to fill NaN values.

        Warnings
        --------
        Note that floating point NaNs (Not a Number) are not missing values.
        To replace missing values, use :func:`fill_null`.

        See Also
        --------
        fill_null

        Examples
        --------
        >>> s = pl.Series("a", [1, 2, 3, float("nan")])
        >>> s.fill_nan(0)
        shape: (4,)
        Series: 'a' [f64]
        [
                1.0
                2.0
                3.0
                0.0
        ]
        """

    def fill_null(
        self,
        value: Any | Expr | None = None,
        strategy: FillNullStrategy | None = None,
        limit: int | None = None,
    ) -> Series:
        """
        Fill null values using the specified value or strategy.

        Parameters
        ----------
        value
            Value used to fill null values.
        strategy : {None, 'forward', 'backward', 'min', 'max', 'mean', 'zero', 'one'}
            Strategy used to fill null values.
        limit
            Number of consecutive null values to fill when using the 'forward' or
            'backward' strategy.

        See Also
        --------
        fill_nan

        Examples
        --------
        >>> s = pl.Series("a", [1, 2, 3, None])
        >>> s.fill_null(strategy="forward")
        shape: (4,)
        Series: 'a' [i64]
        [
            1
            2
            3
            3
        ]
        >>> s.fill_null(strategy="min")
        shape: (4,)
        Series: 'a' [i64]
        [
            1
            2
            3
            1
        ]
        >>> s = pl.Series("b", ["x", None, "z"])
        >>> s.fill_null(pl.lit(""))
        shape: (3,)
        Series: 'b' [str]
        [
            "x"
            ""
            "z"
        ]
        """

    def floor(self) -> Series:
        """
        Rounds down to the nearest integer value.

        Only works on floating point Series.

        Examples
        --------
        >>> s = pl.Series("a", [1.12345, 2.56789, 3.901234])
        >>> s.floor()
        shape: (3,)
        Series: 'a' [f64]
        [
                1.0
                2.0
                3.0
        ]
        """

    def ceil(self) -> Series:
        """
        Rounds up to the nearest integer value.

        Only works on floating point Series.

        Examples
        --------
        >>> s = pl.Series("a", [1.12345, 2.56789, 3.901234])
        >>> s.ceil()
        shape: (3,)
        Series: 'a' [f64]
        [
                2.0
                3.0
                4.0
        ]
        """

    def round(self, decimals: int = 0) -> Series:
        """
        Round underlying floating point data by `decimals` digits.

        Examples
        --------
        >>> s = pl.Series("a", [1.12345, 2.56789, 3.901234])
        >>> s.round(2)
        shape: (3,)
        Series: 'a' [f64]
        [
                1.12
                2.57
                3.9
        ]

        Parameters
        ----------
        decimals
            number of decimals to round by.
        """

    def round_sig_figs(self, digits: int) -> Series:
        """
        Round to a number of significant figures.

        Parameters
        ----------
        digits
            Number of significant figures to round to.

        Examples
        --------
        >>> s = pl.Series([0.01234, 3.333, 1234.0])
        >>> s.round_sig_figs(2)
        shape: (3,)
        Series: '' [f64]
        [
                0.012
                3.3
                1200.0
        ]
        """

    def dot(self, other: Series | ArrayLike) -> int | float | None:
        """
        Compute the dot/inner product between two Series.

        Examples
        --------
        >>> s = pl.Series("a", [1, 2, 3])
        >>> s2 = pl.Series("b", [4.0, 5.0, 6.0])
        >>> s.dot(s2)
        32.0

        Parameters
        ----------
        other
            Series (or array) to compute dot product with.
        """
        if not isinstance(other, Series):
            other = Series(other)
        if len(self) != len(other):
            n, m = len(self), len(other)
            msg = f"Series length mismatch: expected {n!r}, found {m!r}"
            raise ShapeError(msg)
        return self._s.dot(other._s)

    def mode(self) -> Series:
        """
        Compute the most occurring value(s).

        Can return multiple Values.

        Examples
        --------
        >>> s = pl.Series("a", [1, 2, 2, 3])
        >>> s.mode()
        shape: (1,)
        Series: 'a' [i64]
        [
                2
        ]
        """

    def sign(self) -> Series:
        """
        Compute the element-wise indication of the sign.

        The returned values can be -1, 0, or 1:

        * -1 if x  < 0.
        *  0 if x == 0.
        *  1 if x  > 0.

        (null values are preserved as-is).

        Examples
        --------
        >>> s = pl.Series("a", [-9.0, -0.0, 0.0, 4.0, None])
        >>> s.sign()
        shape: (5,)
        Series: 'a' [i64]
        [
                -1
                0
                0
                1
                null
        ]
        """

    def sin(self) -> Series:
        """
        Compute the element-wise value for the sine.

        Examples
        --------
        >>> import math
        >>> s = pl.Series("a", [0.0, math.pi / 2.0, math.pi])
        >>> s.sin()
        shape: (3,)
        Series: 'a' [f64]
        [
            0.0
            1.0
            1.2246e-16
        ]
        """

    def cos(self) -> Series:
        """
        Compute the element-wise value for the cosine.

        Examples
        --------
        >>> import math
        >>> s = pl.Series("a", [0.0, math.pi / 2.0, math.pi])
        >>> s.cos()
        shape: (3,)
        Series: 'a' [f64]
        [
            1.0
            6.1232e-17
            -1.0
        ]
        """

    def tan(self) -> Series:
        """
        Compute the element-wise value for the tangent.

        Examples
        --------
        >>> import math
        >>> s = pl.Series("a", [0.0, math.pi / 2.0, math.pi])
        >>> s.tan()
        shape: (3,)
        Series: 'a' [f64]
        [
            0.0
            1.6331e16
            -1.2246e-16
        ]
        """

    def cot(self) -> Series:
        """
        Compute the element-wise value for the cotangent.

        Examples
        --------
        >>> import math
        >>> s = pl.Series("a", [0.0, math.pi / 2.0, math.pi])
        >>> s.cot()
        shape: (3,)
        Series: 'a' [f64]
        [
            inf
            6.1232e-17
            -8.1656e15
        ]
        """

    def arcsin(self) -> Series:
        """
        Compute the element-wise value for the inverse sine.

        Examples
        --------
        >>> s = pl.Series("a", [1.0, 0.0, -1.0])
        >>> s.arcsin()
        shape: (3,)
        Series: 'a' [f64]
        [
            1.570796
            0.0
            -1.570796
        ]
        """

    def arccos(self) -> Series:
        """
        Compute the element-wise value for the inverse cosine.

        Examples
        --------
        >>> s = pl.Series("a", [1.0, 0.0, -1.0])
        >>> s.arccos()
        shape: (3,)
        Series: 'a' [f64]
        [
            0.0
            1.570796
            3.141593
        ]
        """

    def arctan(self) -> Series:
        """
        Compute the element-wise value for the inverse tangent.

        Examples
        --------
        >>> s = pl.Series("a", [1.0, 0.0, -1.0])
        >>> s.arctan()
        shape: (3,)
        Series: 'a' [f64]
        [
            0.785398
            0.0
            -0.785398
        ]
        """

    def arcsinh(self) -> Series:
        """
        Compute the element-wise value for the inverse hyperbolic sine.

        Examples
        --------
        >>> s = pl.Series("a", [1.0, 0.0, -1.0])
        >>> s.arcsinh()
        shape: (3,)
        Series: 'a' [f64]
        [
            0.881374
            0.0
            -0.881374
        ]
        """

    def arccosh(self) -> Series:
        """
        Compute the element-wise value for the inverse hyperbolic cosine.

        Examples
        --------
        >>> s = pl.Series("a", [5.0, 1.0, 0.0, -1.0])
        >>> s.arccosh()
        shape: (4,)
        Series: 'a' [f64]
        [
            2.292432
            0.0
            NaN
            NaN
        ]
        """

    def arctanh(self) -> Series:
        """
        Compute the element-wise value for the inverse hyperbolic tangent.

        Examples
        --------
        >>> s = pl.Series("a", [2.0, 1.0, 0.5, 0.0, -0.5, -1.0, -1.1])
        >>> s.arctanh()
        shape: (7,)
        Series: 'a' [f64]
        [
            NaN
            inf
            0.549306
            0.0
            -0.549306
            -inf
            NaN
        ]
        """

    def sinh(self) -> Series:
        """
        Compute the element-wise value for the hyperbolic sine.

        Examples
        --------
        >>> s = pl.Series("a", [1.0, 0.0, -1.0])
        >>> s.sinh()
        shape: (3,)
        Series: 'a' [f64]
        [
            1.175201
            0.0
            -1.175201
        ]
        """

    def cosh(self) -> Series:
        """
        Compute the element-wise value for the hyperbolic cosine.

        Examples
        --------
        >>> s = pl.Series("a", [1.0, 0.0, -1.0])
        >>> s.cosh()
        shape: (3,)
        Series: 'a' [f64]
        [
            1.543081
            1.0
            1.543081
        ]
        """

    def tanh(self) -> Series:
        """
        Compute the element-wise value for the hyperbolic tangent.

        Examples
        --------
        >>> s = pl.Series("a", [1.0, 0.0, -1.0])
        >>> s.tanh()
        shape: (3,)
        Series: 'a' [f64]
        [
            0.761594
            0.0
            -0.761594
        ]
        """

    def map_elements(
        self,
        function: Callable[[Any], Any],
        return_dtype: PolarsDataType | None = None,
        *,
        skip_nulls: bool = True,
    ) -> Self:
        """
        Map a custom/user-defined function (UDF) over elements in this Series.

        .. warning::
            This method is much slower than the native expressions API.
            Only use it if you cannot implement your logic otherwise.

            Suppose that the function is: `x ↦ sqrt(x)`:

            - For mapping elements of a series, consider: `s.sqrt()`.
            - For mapping inner elements of lists, consider:
              `s.list.eval(pl.element().sqrt())`.

        If the function returns a different datatype, the return_dtype arg should
        be set, otherwise the method will fail.

        Implementing logic using a Python function is almost always *significantly*
        slower and more memory intensive than implementing the same logic using
        the native expression API because:

        - The native expression engine runs in Rust; UDFs run in Python.
        - Use of Python UDFs forces the DataFrame to be materialized in memory.
        - Polars-native expressions can be parallelised (UDFs typically cannot).
        - Polars-native expressions can be logically optimised (UDFs cannot).

        Wherever possible you should strongly prefer the native expression API
        to achieve the best performance.

        Parameters
        ----------
        function
            Custom function or lambda.
        return_dtype
            Output datatype.
            If not set, the dtype will be inferred based on the first non-null value
            that is returned by the function.
        skip_nulls
            Nulls will be skipped and not passed to the python function.
            This is faster because python can be skipped and because we call
            more specialized functions.

        Warnings
        --------
        If `return_dtype` is not provided, this may lead to unexpected results.
        We allow this, but it is considered a bug in the user's query.

        Notes
        -----
        If your function is expensive and you don't want it to be called more than
        once for a given input, consider applying an `@lru_cache` decorator to it.
        If your data is suitable you may achieve *significant* speedups.

        Examples
        --------
        >>> s = pl.Series("a", [1, 2, 3])
        >>> s.map_elements(lambda x: x + 10, return_dtype=pl.Int64)  # doctest: +SKIP
        shape: (3,)
        Series: 'a' [i64]
        [
                11
                12
                13
        ]

        Returns
        -------
        Series
        """
        from polars._utils.udfs import warn_on_inefficient_map

        if return_dtype is None:
            pl_return_dtype = None
        else:
            pl_return_dtype = py_type_to_dtype(return_dtype)

        warn_on_inefficient_map(function, columns=[self.name], map_target="series")
        return self._from_pyseries(
            self._s.apply_lambda(function, pl_return_dtype, skip_nulls)
        )

    @deprecate_renamed_parameter("periods", "n", version="0.19.11")
    def shift(self, n: int = 1, *, fill_value: IntoExpr | None = None) -> Series:
        """
        Shift values by the given number of indices.

        Parameters
        ----------
        n
            Number of indices to shift forward. If a negative value is passed, values
            are shifted in the opposite direction instead.
        fill_value
            Fill the resulting null values with this value. Accepts expression input.
            Non-expression inputs are parsed as literals.

        Notes
        -----
        This method is similar to the `LAG` operation in SQL when the value for `n`
        is positive. With a negative value for `n`, it is similar to `LEAD`.

        Examples
        --------
        By default, values are shifted forward by one index.

        >>> s = pl.Series([1, 2, 3, 4])
        >>> s.shift()
        shape: (4,)
        Series: '' [i64]
        [
                null
                1
                2
                3
        ]

        Pass a negative value to shift in the opposite direction instead.

        >>> s.shift(-2)
        shape: (4,)
        Series: '' [i64]
        [
                3
                4
                null
                null
        ]

        Specify `fill_value` to fill the resulting null values.

        >>> s.shift(-2, fill_value=100)
        shape: (4,)
        Series: '' [i64]
        [
                3
                4
                100
                100
        ]
        """

    def zip_with(self, mask: Series, other: Series) -> Self:
        """
        Take values from self or other based on the given mask.

        Where mask evaluates true, take values from self. Where mask evaluates false,
        take values from other.

        Parameters
        ----------
        mask
            Boolean Series.
        other
            Series of same type.

        Returns
        -------
        Series

        Examples
        --------
        >>> s1 = pl.Series([1, 2, 3, 4, 5])
        >>> s2 = pl.Series([5, 4, 3, 2, 1])
        >>> s1.zip_with(s1 < s2, s2)
        shape: (5,)
        Series: '' [i64]
        [
                1
                2
                3
                2
                1
        ]
        >>> mask = pl.Series([True, False, True, False, True])
        >>> s1.zip_with(mask, s2)
        shape: (5,)
        Series: '' [i64]
        [
                1
                4
                3
                2
                5
        ]
        """
        return self._from_pyseries(self._s.zip_with(mask._s, other._s))

    @unstable()
    def rolling_min(
        self,
        window_size: int,
        weights: list[float] | None = None,
        min_periods: int | None = None,
        *,
        center: bool = False,
    ) -> Series:
        """
        Apply a rolling min (moving min) over the values in this array.

        .. warning::
            This functionality is considered **unstable**. It may be changed
            at any point without it being considered a breaking change.

        A window of length `window_size` will traverse the array. The values that fill
        this window will (optionally) be multiplied with the weights given by the
        `weight` vector. The resulting values will be aggregated to their min.

        The window at a given row will include the row itself and the `window_size - 1`
        elements before it.

        Parameters
        ----------
        window_size
            The length of the window.
        weights
            An optional slice with the same length as the window that will be multiplied
            elementwise with the values in the window.
        min_periods
            The number of values in the window that should be non-null before computing
            a result. If None, it will be set equal to:

            - the window size, if `window_size` is a fixed integer
            - 1, if `window_size` is a dynamic temporal size
        center
            Set the labels at the center of the window

        Examples
        --------
        >>> s = pl.Series("a", [100, 200, 300, 400, 500])
        >>> s.rolling_min(window_size=3)
        shape: (5,)
        Series: 'a' [i64]
        [
            null
            null
            100
            200
            300
        ]
        """
        return (
            self.to_frame()
            .select(
                F.col(self.name).rolling_min(
                    window_size, weights, min_periods, center=center
                )
            )
            .to_series()
        )

    @unstable()
    def rolling_max(
        self,
        window_size: int,
        weights: list[float] | None = None,
        min_periods: int | None = None,
        *,
        center: bool = False,
    ) -> Series:
        """
        Apply a rolling max (moving max) over the values in this array.

        .. warning::
            This functionality is considered **unstable**. It may be changed
            at any point without it being considered a breaking change.

        A window of length `window_size` will traverse the array. The values that fill
        this window will (optionally) be multiplied with the weights given by the
        `weight` vector. The resulting values will be aggregated to their max.

        The window at a given row will include the row itself and the `window_size - 1`
        elements before it.

        Parameters
        ----------
        window_size
            The length of the window.
        weights
            An optional slice with the same length as the window that will be multiplied
            elementwise with the values in the window.
        min_periods
            The number of values in the window that should be non-null before computing
            a result. If None, it will be set equal to:

            - the window size, if `window_size` is a fixed integer
            - 1, if `window_size` is a dynamic temporal size
        center
            Set the labels at the center of the window

        Examples
        --------
        >>> s = pl.Series("a", [100, 200, 300, 400, 500])
        >>> s.rolling_max(window_size=2)
        shape: (5,)
        Series: 'a' [i64]
        [
            null
            200
            300
            400
            500
        ]
        """
        return (
            self.to_frame()
            .select(
                F.col(self.name).rolling_max(
                    window_size, weights, min_periods, center=center
                )
            )
            .to_series()
        )

    @unstable()
    def rolling_mean(
        self,
        window_size: int,
        weights: list[float] | None = None,
        min_periods: int | None = None,
        *,
        center: bool = False,
    ) -> Series:
        """
        Apply a rolling mean (moving mean) over the values in this array.

        .. warning::
            This functionality is considered **unstable**. It may be changed
            at any point without it being considered a breaking change.

        A window of length `window_size` will traverse the array. The values that fill
        this window will (optionally) be multiplied with the weights given by the
        `weight` vector. The resulting values will be aggregated to their mean.

        The window at a given row will include the row itself and the `window_size - 1`
        elements before it.

        Parameters
        ----------
        window_size
            The length of the window.
        weights
            An optional slice with the same length as the window that will be multiplied
            elementwise with the values in the window.
        min_periods
            The number of values in the window that should be non-null before computing
            a result. If None, it will be set equal to:

            - the window size, if `window_size` is a fixed integer
            - 1, if `window_size` is a dynamic temporal size
        center
            Set the labels at the center of the window

        Examples
        --------
        >>> s = pl.Series("a", [100, 200, 300, 400, 500])
        >>> s.rolling_mean(window_size=2)
        shape: (5,)
        Series: 'a' [f64]
        [
            null
            150.0
            250.0
            350.0
            450.0
        ]
        """
        return (
            self.to_frame()
            .select(
                F.col(self.name).rolling_mean(
                    window_size, weights, min_periods, center=center
                )
            )
            .to_series()
        )

    @unstable()
    def rolling_sum(
        self,
        window_size: int,
        weights: list[float] | None = None,
        min_periods: int | None = None,
        *,
        center: bool = False,
    ) -> Series:
        """
        Apply a rolling sum (moving sum) over the values in this array.

        .. warning::
            This functionality is considered **unstable**. It may be changed
            at any point without it being considered a breaking change.

        A window of length `window_size` will traverse the array. The values that fill
        this window will (optionally) be multiplied with the weights given by the
        `weight` vector. The resulting values will be aggregated to their sum.

        The window at a given row will include the row itself and the `window_size - 1`
        elements before it.

        Parameters
        ----------
        window_size
            The length of the window.
        weights
            An optional slice with the same length of the window that will be multiplied
            elementwise with the values in the window.
        min_periods
            The number of values in the window that should be non-null before computing
            a result. If None, it will be set equal to:

            - the window size, if `window_size` is a fixed integer
            - 1, if `window_size` is a dynamic temporal size
        center
            Set the labels at the center of the window

        Examples
        --------
        >>> s = pl.Series("a", [1, 2, 3, 4, 5])
        >>> s.rolling_sum(window_size=2)
        shape: (5,)
        Series: 'a' [i64]
        [
                null
                3
                5
                7
                9
        ]
        """
        return (
            self.to_frame()
            .select(
                F.col(self.name).rolling_sum(
                    window_size, weights, min_periods, center=center
                )
            )
            .to_series()
        )

    @unstable()
    def rolling_std(
        self,
        window_size: int,
        weights: list[float] | None = None,
        min_periods: int | None = None,
        *,
        center: bool = False,
        ddof: int = 1,
    ) -> Series:
        """
        Compute a rolling std dev.

        .. warning::
            This functionality is considered **unstable**. It may be changed
            at any point without it being considered a breaking change.

        A window of length `window_size` will traverse the array. The values that fill
        this window will (optionally) be multiplied with the weights given by the
        `weight` vector. The resulting values will be aggregated to their std dev.

        The window at a given row will include the row itself and the `window_size - 1`
        elements before it.

        Parameters
        ----------
        window_size
            The length of the window.
        weights
            An optional slice with the same length as the window that will be multiplied
            elementwise with the values in the window.
        min_periods
            The number of values in the window that should be non-null before computing
            a result. If None, it will be set equal to:

            - the window size, if `window_size` is a fixed integer
            - 1, if `window_size` is a dynamic temporal size
        center
            Set the labels at the center of the window
        ddof
            "Delta Degrees of Freedom": The divisor for a length N window is N - ddof

        Examples
        --------
        >>> s = pl.Series("a", [1.0, 2.0, 3.0, 4.0, 6.0, 8.0])
        >>> s.rolling_std(window_size=3)
        shape: (6,)
        Series: 'a' [f64]
        [
                null
                null
                1.0
                1.0
                1.527525
                2.0
        ]
        """
        return (
            self.to_frame()
            .select(
                F.col(self.name).rolling_std(
                    window_size, weights, min_periods, center=center, ddof=ddof
                )
            )
            .to_series()
        )

    @unstable()
    def rolling_var(
        self,
        window_size: int,
        weights: list[float] | None = None,
        min_periods: int | None = None,
        *,
        center: bool = False,
        ddof: int = 1,
    ) -> Series:
        """
        Compute a rolling variance.

        .. warning::
            This functionality is considered **unstable**. It may be changed
            at any point without it being considered a breaking change.

        A window of length `window_size` will traverse the array. The values that fill
        this window will (optionally) be multiplied with the weights given by the
        `weight` vector. The resulting values will be aggregated to their variance.

        The window at a given row will include the row itself and the `window_size - 1`
        elements before it.

        Parameters
        ----------
        window_size
            The length of the window.
        weights
            An optional slice with the same length as the window that will be multiplied
            elementwise with the values in the window.
        min_periods
            The number of values in the window that should be non-null before computing
            a result. If None, it will be set equal to:

            - the window size, if `window_size` is a fixed integer
            - 1, if `window_size` is a dynamic temporal size
        center
            Set the labels at the center of the window
        ddof
            "Delta Degrees of Freedom": The divisor for a length N window is N - ddof

        Examples
        --------
        >>> s = pl.Series("a", [1.0, 2.0, 3.0, 4.0, 6.0, 8.0])
        >>> s.rolling_var(window_size=3)
        shape: (6,)
        Series: 'a' [f64]
        [
                null
                null
                1.0
                1.0
                2.333333
                4.0
        ]
        """
        return (
            self.to_frame()
            .select(
                F.col(self.name).rolling_var(
                    window_size, weights, min_periods, center=center, ddof=ddof
                )
            )
            .to_series()
        )

    @unstable()
    def rolling_map(
        self,
        function: Callable[[Series], Any],
        window_size: int,
        weights: list[float] | None = None,
        min_periods: int | None = None,
        *,
        center: bool = False,
    ) -> Series:
        """
        Compute a custom rolling window function.

        .. warning::
            This functionality is considered **unstable**. It may be changed
            at any point without it being considered a breaking change.

        Parameters
        ----------
        function
            Custom aggregation function.
        window_size
            Size of the window. The window at a given row will include the row
            itself and the `window_size - 1` elements before it.
        weights
            A list of weights with the same length as the window that will be multiplied
            elementwise with the values in the window.
        min_periods
            The number of values in the window that should be non-null before computing
            a result. If None, it will be set equal to:

            - the window size, if `window_size` is a fixed integer
            - 1, if `window_size` is a dynamic temporal size
        center
            Set the labels at the center of the window.

        Warnings
        --------
        Computing custom functions is extremely slow. Use specialized rolling
        functions such as :func:`Series.rolling_sum` if at all possible.

        Examples
        --------
        >>> from numpy import nansum
        >>> s = pl.Series([11.0, 2.0, 9.0, float("nan"), 8.0])
        >>> s.rolling_map(nansum, window_size=3)
        shape: (5,)
        Series: '' [f64]
        [
                null
                null
                22.0
                11.0
                17.0
        ]
        """

    @unstable()
    def rolling_median(
        self,
        window_size: int,
        weights: list[float] | None = None,
        min_periods: int | None = None,
        *,
        center: bool = False,
    ) -> Series:
        """
        Compute a rolling median.

        .. warning::
            This functionality is considered **unstable**. It may be changed
            at any point without it being considered a breaking change.

        Parameters
        ----------
        window_size
            The length of the window.
        weights
            An optional slice with the same length as the window that will be multiplied
            elementwise with the values in the window.
        min_periods
            The number of values in the window that should be non-null before computing
            a result. If None, it will be set equal to:

            - the window size, if `window_size` is a fixed integer
            - 1, if `window_size` is a dynamic temporal size
        center
            Set the labels at the center of the window

        The window at a given row will include the row itself and the `window_size - 1`
        elements before it.

        Examples
        --------
        >>> s = pl.Series("a", [1.0, 2.0, 3.0, 4.0, 6.0, 8.0])
        >>> s.rolling_median(window_size=3)
        shape: (6,)
        Series: 'a' [f64]
        [
                null
                null
                2.0
                3.0
                4.0
                6.0
        ]
        """
        if min_periods is None:
            min_periods = window_size

        return (
            self.to_frame()
            .select(
                F.col(self.name).rolling_median(
                    window_size, weights, min_periods, center=center
                )
            )
            .to_series()
        )

    @unstable()
    def rolling_quantile(
        self,
        quantile: float,
        interpolation: RollingInterpolationMethod = "nearest",
        window_size: int = 2,
        weights: list[float] | None = None,
        min_periods: int | None = None,
        *,
        center: bool = False,
    ) -> Series:
        """
        Compute a rolling quantile.

        .. warning::
            This functionality is considered **unstable**. It may be changed
            at any point without it being considered a breaking change.

        The window at a given row will include the row itself and the `window_size - 1`
        elements before it.

        Parameters
        ----------
        quantile
            Quantile between 0.0 and 1.0.
        interpolation : {'nearest', 'higher', 'lower', 'midpoint', 'linear'}
            Interpolation method.
        window_size
            The length of the window.
        weights
            An optional slice with the same length as the window that will be multiplied
            elementwise with the values in the window.
        min_periods
            The number of values in the window that should be non-null before computing
            a result. If None, it will be set equal to:

            - the window size, if `window_size` is a fixed integer
            - 1, if `window_size` is a dynamic temporal size
        center
            Set the labels at the center of the window

        Examples
        --------
        >>> s = pl.Series("a", [1.0, 2.0, 3.0, 4.0, 6.0, 8.0])
        >>> s.rolling_quantile(quantile=0.33, window_size=3)
        shape: (6,)
        Series: 'a' [f64]
        [
                null
                null
                1.0
                2.0
                3.0
                4.0
        ]
        >>> s.rolling_quantile(quantile=0.33, interpolation="linear", window_size=3)
        shape: (6,)
        Series: 'a' [f64]
        [
                null
                null
                1.66
                2.66
                3.66
                5.32
        ]
        """
        if min_periods is None:
            min_periods = window_size

        return (
            self.to_frame()
            .select(
                F.col(self.name).rolling_quantile(
                    quantile,
                    interpolation,
                    window_size,
                    weights,
                    min_periods,
                    center=center,
                )
            )
            .to_series()
        )

    @unstable()
    def rolling_skew(self, window_size: int, *, bias: bool = True) -> Series:
        """
        Compute a rolling skew.

        .. warning::
            This functionality is considered **unstable**. It may be changed
            at any point without it being considered a breaking change.

        The window at a given row includes the row itself and the
        `window_size - 1` elements before it.

        Parameters
        ----------
        window_size
            Integer size of the rolling window.
        bias
            If False, the calculations are corrected for statistical bias.

        Examples
        --------
        >>> pl.Series([1, 4, 2, 9]).rolling_skew(3)
        shape: (4,)
        Series: '' [f64]
        [
            null
            null
            0.381802
            0.47033
        ]

        Note how the values match

        >>> pl.Series([1, 4, 2]).skew(), pl.Series([4, 2, 9]).skew()
        (0.38180177416060584, 0.47033046033698594)
        """

    def sample(
        self,
        n: int | None = None,
        *,
        fraction: float | None = None,
        with_replacement: bool = False,
        shuffle: bool = False,
        seed: int | None = None,
    ) -> Series:
        """
        Sample from this Series.

        Parameters
        ----------
        n
            Number of items to return. Cannot be used with `fraction`. Defaults to 1 if
            `fraction` is None.
        fraction
            Fraction of items to return. Cannot be used with `n`.
        with_replacement
            Allow values to be sampled more than once.
        shuffle
            Shuffle the order of sampled data points.
        seed
            Seed for the random number generator. If set to None (default), a
            random seed is generated for each sample operation.

        Examples
        --------
        >>> s = pl.Series("a", [1, 2, 3, 4, 5])
        >>> s.sample(2, seed=0)  # doctest: +IGNORE_RESULT
        shape: (2,)
        Series: 'a' [i64]
        [
            1
            5
        ]
        """

    def peak_max(self) -> Self:
        """
        Get a boolean mask of the local maximum peaks.

        Examples
        --------
        >>> s = pl.Series("a", [1, 2, 3, 4, 5])
        >>> s.peak_max()
        shape: (5,)
        Series: 'a' [bool]
        [
                false
                false
                false
                false
                true
        ]
        """

    def peak_min(self) -> Self:
        """
        Get a boolean mask of the local minimum peaks.

        Examples
        --------
        >>> s = pl.Series("a", [4, 1, 3, 2, 5])
        >>> s.peak_min()
        shape: (5,)
        Series: 'a' [bool]
        [
            false
            true
            false
            true
            false
        ]
        """

    def n_unique(self) -> int:
        """
        Count the number of unique values in this Series.

        Examples
        --------
        >>> s = pl.Series("a", [1, 2, 2, 3])
        >>> s.n_unique()
        3
        """
        return self._s.n_unique()

    def shrink_to_fit(self, *, in_place: bool = False) -> Series:
        """
        Shrink Series memory usage.

        Shrinks the underlying array capacity to exactly fit the actual data.
        (Note that this function does not change the Series data type).
        """
        if in_place:
            self._s.shrink_to_fit()
            return self
        else:
            series = self.clone()
            series._s.shrink_to_fit()
            return series

    def hash(
        self,
        seed: int = 0,
        seed_1: int | None = None,
        seed_2: int | None = None,
        seed_3: int | None = None,
    ) -> Series:
        """
        Hash the Series.

        The hash value is of type `UInt64`.

        Parameters
        ----------
        seed
            Random seed parameter. Defaults to 0.
        seed_1
            Random seed parameter. Defaults to `seed` if not set.
        seed_2
            Random seed parameter. Defaults to `seed` if not set.
        seed_3
            Random seed parameter. Defaults to `seed` if not set.

        Notes
        -----
        This implementation of `hash` does not guarantee stable results
        across different Polars versions. Its stability is only guaranteed within a
        single version.

        Examples
        --------
        >>> s = pl.Series("a", [1, 2, 3])
        >>> s.hash(seed=42)  # doctest: +IGNORE_RESULT
        shape: (3,)
        Series: 'a' [u64]
        [
            10734580197236529959
            3022416320763508302
            13756996518000038261
        ]
        """

    def reinterpret(self, *, signed: bool = True) -> Series:
        """
        Reinterpret the underlying bits as a signed/unsigned integer.

        This operation is only allowed for 64bit integers. For lower bits integers,
        you can safely use that cast operation.

        Parameters
        ----------
        signed
            If True, reinterpret as `pl.Int64`. Otherwise, reinterpret as `pl.UInt64`.

        Examples
        --------
        >>> s = pl.Series("a", [1, 2, 3])
        >>> s
        shape: (3,)
        Series: 'a' [i64]
        [
                1
                2
                3
        ]
        >>> s.reinterpret(signed=False)
        shape: (3,)
        Series: 'a' [u64]
        [
                1
                2
                3
        ]
        """

    def interpolate(self, method: InterpolationMethod = "linear") -> Series:
        """
        Fill null values using interpolation.

        Parameters
        ----------
        method : {'linear', 'nearest'}
            Interpolation method.

        Examples
        --------
        >>> s = pl.Series("a", [1, 2, None, None, 5])
        >>> s.interpolate()
        shape: (5,)
        Series: 'a' [f64]
        [
            1.0
            2.0
            3.0
            4.0
            5.0
        ]
        """

    def abs(self) -> Series:
        """
        Compute absolute values.

        Same as `abs(series)`.

        Examples
        --------
        >>> s = pl.Series([1, -2, -3])
        >>> s.abs()
        shape: (3,)
        Series: '' [i64]
        [
            1
            2
            3
        ]
        """

    def rank(
        self,
        method: RankMethod = "average",
        *,
        descending: bool = False,
        seed: int | None = None,
    ) -> Series:
        """
        Assign ranks to data, dealing with ties appropriately.

        Parameters
        ----------
        method : {'average', 'min', 'max', 'dense', 'ordinal', 'random'}
            The method used to assign ranks to tied elements.
            The following methods are available (default is 'average'):

            - 'average' : The average of the ranks that would have been assigned to
              all the tied values is assigned to each value.
            - 'min' : The minimum of the ranks that would have been assigned to all
              the tied values is assigned to each value. (This is also referred to
              as "competition" ranking.)
            - 'max' : The maximum of the ranks that would have been assigned to all
              the tied values is assigned to each value.
            - 'dense' : Like 'min', but the rank of the next highest element is
              assigned the rank immediately after those assigned to the tied
              elements.
            - 'ordinal' : All values are given a distinct rank, corresponding to
              the order that the values occur in the Series.
            - 'random' : Like 'ordinal', but the rank for ties is not dependent
              on the order that the values occur in the Series.
        descending
            Rank in descending order.
        seed
            If `method="random"`, use this as seed.

        Examples
        --------
        The 'average' method:

        >>> s = pl.Series("a", [3, 6, 1, 1, 6])
        >>> s.rank()
        shape: (5,)
        Series: 'a' [f64]
        [
            3.0
            4.5
            1.5
            1.5
            4.5
        ]

        The 'ordinal' method:

        >>> s = pl.Series("a", [3, 6, 1, 1, 6])
        >>> s.rank("ordinal")
        shape: (5,)
        Series: 'a' [u32]
        [
            3
            4
            1
            2
            5
        ]
        """

    def diff(self, n: int = 1, null_behavior: NullBehavior = "ignore") -> Series:
        """
        Calculate the first discrete difference between shifted items.

        Parameters
        ----------
        n
            Number of slots to shift.
        null_behavior : {'ignore', 'drop'}
            How to handle null values.

        Examples
        --------
        >>> s = pl.Series("s", values=[20, 10, 30, 25, 35], dtype=pl.Int8)
        >>> s.diff()
        shape: (5,)
        Series: 's' [i8]
        [
            null
            -10
            20
            -5
            10
        ]

        >>> s.diff(n=2)
        shape: (5,)
        Series: 's' [i8]
        [
            null
            null
            10
            15
            5
        ]

        >>> s.diff(n=2, null_behavior="drop")
        shape: (3,)
        Series: 's' [i8]
        [
            10
            15
            5
        ]
        """

    def pct_change(self, n: int | IntoExprColumn = 1) -> Series:
        """
        Computes percentage change between values.

        Percentage change (as fraction) between current element and most-recent
        non-null element at least `n` period(s) before the current element.

        Computes the change from the previous row by default.

        Parameters
        ----------
        n
            periods to shift for forming percent change.

        Examples
        --------
        >>> pl.Series(range(10)).pct_change()
        shape: (10,)
        Series: '' [f64]
        [
            null
            inf
            1.0
            0.5
            0.333333
            0.25
            0.2
            0.166667
            0.142857
            0.125
        ]

        >>> pl.Series([1, 2, 4, 8, 16, 32, 64, 128, 256, 512]).pct_change(2)
        shape: (10,)
        Series: '' [f64]
        [
            null
            null
            3.0
            3.0
            3.0
            3.0
            3.0
            3.0
            3.0
            3.0
        ]
        """

    def skew(self, *, bias: bool = True) -> float | None:
        r"""
        Compute the sample skewness of a data set.

        For normally distributed data, the skewness should be about zero. For
        unimodal continuous distributions, a skewness value greater than zero means
        that there is more weight in the right tail of the distribution. The
        function `skewtest` can be used to determine if the skewness value
        is close enough to zero, statistically speaking.


        See scipy.stats for more information.

        Parameters
        ----------
        bias : bool, optional
            If False, the calculations are corrected for statistical bias.

        Notes
        -----
        The sample skewness is computed as the Fisher-Pearson coefficient
        of skewness, i.e.

        .. math:: g_1=\frac{m_3}{m_2^{3/2}}

        where

        .. math:: m_i=\frac{1}{N}\sum_{n=1}^N(x[n]-\bar{x})^i

        is the biased sample :math:`i\texttt{th}` central moment, and
        :math:`\bar{x}` is
        the sample mean.  If `bias` is False, the calculations are
        corrected for bias and the value computed is the adjusted
        Fisher-Pearson standardized moment coefficient, i.e.

        .. math::
            G_1 = \frac{k_3}{k_2^{3/2}} = \frac{\sqrt{N(N-1)}}{N-2}\frac{m_3}{m_2^{3/2}}

        Examples
        --------
        >>> s = pl.Series([1, 2, 2, 4, 5])
        >>> s.skew()
        0.34776706224699483
        """
        return self._s.skew(bias)

    def kurtosis(self, *, fisher: bool = True, bias: bool = True) -> float | None:
        """
        Compute the kurtosis (Fisher or Pearson) of a dataset.

        Kurtosis is the fourth central moment divided by the square of the
        variance. If Fisher's definition is used, then 3.0 is subtracted from
        the result to give 0.0 for a normal distribution.
        If bias is False then the kurtosis is calculated using k statistics to
        eliminate bias coming from biased moment estimators

        See scipy.stats for more information

        Parameters
        ----------
        fisher : bool, optional
            If True, Fisher's definition is used (normal ==> 0.0). If False,
            Pearson's definition is used (normal ==> 3.0).
        bias : bool, optional
            If False, the calculations are corrected for statistical bias.

        Examples
        --------
        >>> s = pl.Series("grades", [66, 79, 54, 97, 96, 70, 69, 85, 93, 75])
        >>> s.kurtosis()
        -1.0522623626787952
        >>> s.kurtosis(fisher=False)
        1.9477376373212048
        >>> s.kurtosis(fisher=False, bias=False)
        2.1040361802642726
        """
        return self._s.kurtosis(fisher, bias)

    def clip(
        self,
        lower_bound: NumericLiteral | TemporalLiteral | IntoExprColumn | None = None,
        upper_bound: NumericLiteral | TemporalLiteral | IntoExprColumn | None = None,
    ) -> Series:
        """
        Set values outside the given boundaries to the boundary value.

        Parameters
        ----------
        lower_bound
            Lower bound. Accepts expression input.
            Non-expression inputs are parsed as literals.
            If set to `None` (default), no lower bound is applied.
        upper_bound
            Upper bound. Accepts expression input.
            Non-expression inputs are parsed as literals.
            If set to `None` (default), no upper bound is applied.

        See Also
        --------
        when

        Notes
        -----
        This method only works for numeric and temporal columns. To clip other data
        types, consider writing a `when-then-otherwise` expression. See :func:`when`.

        Examples
        --------
        Specifying both a lower and upper bound:

        >>> s = pl.Series([-50, 5, 50, None])
        >>> s.clip(1, 10)
        shape: (4,)
        Series: '' [i64]
        [
                1
                5
                10
                null
        ]

        Specifying only a single bound:

        >>> s.clip(upper_bound=10)
        shape: (4,)
        Series: '' [i64]
        [
                -50
                5
                10
                null
        ]
        """

    def lower_bound(self) -> Self:
        """
        Return the lower bound of this Series' dtype as a unit Series.

        See Also
        --------
        upper_bound : return the upper bound of the given Series' dtype.

        Examples
        --------
        >>> s = pl.Series("s", [-1, 0, 1], dtype=pl.Int32)
        >>> s.lower_bound()
        shape: (1,)
        Series: 's' [i32]
        [
            -2147483648
        ]

        >>> s = pl.Series("s", [1.0, 2.5, 3.0], dtype=pl.Float32)
        >>> s.lower_bound()
        shape: (1,)
        Series: 's' [f32]
        [
            -inf
        ]
        """

    def upper_bound(self) -> Self:
        """
        Return the upper bound of this Series' dtype as a unit Series.

        See Also
        --------
        lower_bound : return the lower bound of the given Series' dtype.

        Examples
        --------
        >>> s = pl.Series("s", [-1, 0, 1], dtype=pl.Int8)
        >>> s.upper_bound()
        shape: (1,)
        Series: 's' [i8]
        [
            127
        ]

        >>> s = pl.Series("s", [1.0, 2.5, 3.0], dtype=pl.Float64)
        >>> s.upper_bound()
        shape: (1,)
        Series: 's' [f64]
        [
            inf
        ]
        """

    def replace(
        self,
        old: IntoExpr | Sequence[Any] | Mapping[Any, Any],
        new: IntoExpr | Sequence[Any] | NoDefault = no_default,
        *,
        default: IntoExpr | NoDefault = no_default,
        return_dtype: PolarsDataType | None = None,
    ) -> Self:
        """
        Replace values by different values.

        Parameters
        ----------
        old
            Value or sequence of values to replace.
            Also accepts a mapping of values to their replacement as syntactic sugar for
            `replace(old=Series(mapping.keys()), new=Series(mapping.values()))`.
        new
            Value or sequence of values to replace by.
            Length must match the length of `old` or have length 1.
        default
            Set values that were not replaced to this value.
            Defaults to keeping the original value.
            Accepts expression input. Non-expression inputs are parsed as literals.
        return_dtype
            The data type of the resulting Series. If set to `None` (default),
            the data type is determined automatically based on the other inputs.

        See Also
        --------
        str.replace

        Notes
        -----
        The global string cache must be enabled when replacing categorical values.

        Examples
        --------
        Replace a single value by another value. Values that were not replaced remain
        unchanged.

        >>> s = pl.Series([1, 2, 2, 3])
        >>> s.replace(2, 100)
        shape: (4,)
        Series: '' [i64]
        [
                1
                100
                100
                3
        ]

        Replace multiple values by passing sequences to the `old` and `new` parameters.

        >>> s.replace([2, 3], [100, 200])
        shape: (4,)
        Series: '' [i64]
        [
                1
                100
                100
                200
        ]

        Passing a mapping with replacements is also supported as syntactic sugar.
        Specify a default to set all values that were not matched.

        >>> mapping = {2: 100, 3: 200}
        >>> s.replace(mapping, default=-1)
        shape: (4,)
        Series: '' [i64]
        [
                -1
                100
                100
                200
        ]


        The default can be another Series.

        >>> default = pl.Series([2.5, 5.0, 7.5, 10.0])
        >>> s.replace(2, 100, default=default)
        shape: (4,)
        Series: '' [f64]
        [
                2.5
                100.0
                100.0
                10.0
        ]

        Replacing by values of a different data type sets the return type based on
        a combination of the `new` data type and either the original data type or the
        default data type if it was set.

        >>> s = pl.Series(["x", "y", "z"])
        >>> mapping = {"x": 1, "y": 2, "z": 3}
        >>> s.replace(mapping)
        shape: (3,)
        Series: '' [str]
        [
                "1"
                "2"
                "3"
        ]
        >>> s.replace(mapping, default=None)
        shape: (3,)
        Series: '' [i64]
        [
                1
                2
                3
        ]

        Set the `return_dtype` parameter to control the resulting data type directly.

        >>> s.replace(mapping, return_dtype=pl.UInt8)
        shape: (3,)
        Series: '' [u8]
        [
                1
                2
                3
        ]
        """

    def reshape(self, dimensions: tuple[int, ...]) -> Series:
        """
        Reshape this Series to a flat Series or a Series of Lists.

        Parameters
        ----------
        dimensions
            Tuple of the dimension sizes. If a -1 is used in any of the dimensions, that
            dimension is inferred.

        Returns
        -------
        Series
            If a single dimension is given, results in a Series of the original
            data type.
            If a multiple dimensions are given, results in a Series of data type
            :class:`List` with shape (rows, cols).

        See Also
        --------
        Series.list.explode : Explode a list column.

        Examples
        --------
        >>> s = pl.Series("foo", [1, 2, 3, 4, 5, 6, 7, 8, 9])
        >>> s.reshape((3, 3))
        shape: (3,)
        Series: 'foo' [list[i64]]
        [
                [1, 2, 3]
                [4, 5, 6]
                [7, 8, 9]
        ]
        """

    def shuffle(self, seed: int | None = None) -> Series:
        """
        Shuffle the contents of this Series.

        Parameters
        ----------
        seed
            Seed for the random number generator. If set to None (default), a
            random seed is generated each time the shuffle is called.

        Examples
        --------
        >>> s = pl.Series("a", [1, 2, 3])
        >>> s.shuffle(seed=1)
        shape: (3,)
        Series: 'a' [i64]
        [
                2
                1
                3
        ]
        """

    @deprecate_nonkeyword_arguments(version="0.19.10")
    def ewm_mean(
        self,
        com: float | None = None,
        span: float | None = None,
        half_life: float | None = None,
        alpha: float | None = None,
        *,
        adjust: bool = True,
        min_periods: int = 1,
        ignore_nulls: bool | None = None,
    ) -> Series:
        r"""
        Exponentially-weighted moving average.

        Parameters
        ----------
        com
            Specify decay in terms of center of mass, :math:`\gamma`, with

                .. math::
                    \alpha = \frac{1}{1 + \gamma} \; \forall \; \gamma \geq 0
        span
            Specify decay in terms of span, :math:`\theta`, with

                .. math::
                    \alpha = \frac{2}{\theta + 1} \; \forall \; \theta \geq 1
        half_life
            Specify decay in terms of half-life, :math:`\lambda`, with

                .. math::
                    \alpha = 1 - \exp \left\{ \frac{ -\ln(2) }{ \lambda } \right\} \;
                    \forall \; \lambda > 0
        alpha
            Specify smoothing factor alpha directly, :math:`0 < \alpha \leq 1`.
        adjust
            Divide by decaying adjustment factor in beginning periods to account for
            imbalance in relative weightings

                - When `adjust=True` (the default) the EW function is calculated
                  using weights :math:`w_i = (1 - \alpha)^i`
                - When `adjust=False` the EW function is calculated
                  recursively by

                  .. math::
                    y_0 &= x_0 \\
                    y_t &= (1 - \alpha)y_{t - 1} + \alpha x_t
        min_periods
            Minimum number of observations in window required to have a value
            (otherwise result is null).
        ignore_nulls
            Ignore missing values when calculating weights.

                - When `ignore_nulls=False`, weights are based on absolute
                  positions.
                  For example, the weights of :math:`x_0` and :math:`x_2` used in
                  calculating the final weighted average of
                  [:math:`x_0`, None, :math:`x_2`] are
                  :math:`(1-\alpha)^2` and :math:`1` if `adjust=True`, and
                  :math:`(1-\alpha)^2` and :math:`\alpha` if `adjust=False`.

                - When `ignore_nulls=True` (current default), weights are based
                  on relative positions. For example, the weights of
                  :math:`x_0` and :math:`x_2` used in calculating the final weighted
                  average of [:math:`x_0`, None, :math:`x_2`] are
                  :math:`1-\alpha` and :math:`1` if `adjust=True`,
                  and :math:`1-\alpha` and :math:`\alpha` if `adjust=False`.

        Examples
        --------
        >>> s = pl.Series([1, 2, 3])
        >>> s.ewm_mean(com=1, ignore_nulls=False)
        shape: (3,)
        Series: '' [f64]
        [
                1.0
                1.666667
                2.428571
        ]
        """

    def ewm_mean_by(
        self,
        by: str | IntoExpr,
        *,
        half_life: str | timedelta,
    ) -> Series:
        r"""
        Calculate time-based exponentially weighted moving average.

        Given observations :math:`x_1, x_2, \ldots, x_n` at times
        :math:`t_1, t_2, \ldots, t_n`, the EWMA is calculated as

            .. math::

                y_0 &= x_0

                \alpha_i &= \exp(-\lambda(t_i - t_{i-1}))

                y_i &= \alpha_i x_i + (1 - \alpha_i) y_{i-1}; \quad i > 0

        where :math:`\lambda` equals :math:`\ln(2) / \text{half_life}`.

        Parameters
        ----------
        by
            Times to calculate average by. Should be ``DateTime``, ``Date``, ``UInt64``,
            ``UInt32``, ``Int64``, or ``Int32`` data type.
        half_life
            Unit over which observation decays to half its value.

            Can be created either from a timedelta, or
            by using the following string language:

            - 1ns   (1 nanosecond)
            - 1us   (1 microsecond)
            - 1ms   (1 millisecond)
            - 1s    (1 second)
            - 1m    (1 minute)
            - 1h    (1 hour)
            - 1d    (1 day)
            - 1w    (1 week)
            - 1i    (1 index count)

            Or combine them:
            "3d12h4m25s" # 3 days, 12 hours, 4 minutes, and 25 seconds

            Note that `half_life` is treated as a constant duration - calendar
            durations such as months (or even days in the time-zone-aware case)
            are not supported, please express your duration in an approximately
            equivalent number of hours (e.g. '370h' instead of '1mo').
        check_sorted
            Check whether `by` column is sorted.
            Incorrectly setting this to `False` will lead to incorrect output.

        Returns
        -------
        Expr
            Float32 if input is Float32, otherwise Float64.

        Examples
        --------
        >>> from datetime import date, timedelta
        >>> df = pl.DataFrame(
        ...     {
        ...         "values": [0, 1, 2, None, 4],
        ...         "times": [
        ...             date(2020, 1, 1),
        ...             date(2020, 1, 3),
        ...             date(2020, 1, 10),
        ...             date(2020, 1, 15),
        ...             date(2020, 1, 17),
        ...         ],
        ...     }
        ... ).sort("times")
        >>> df["values"].ewm_mean_by(df["times"], half_life="4d")
        shape: (5,)
        Series: 'values' [f64]
        [
                0.0
                0.292893
                1.492474
                null
                3.254508
        ]
        """

    @deprecate_nonkeyword_arguments(version="0.19.10")
    def ewm_std(
        self,
        com: float | None = None,
        span: float | None = None,
        half_life: float | None = None,
        alpha: float | None = None,
        *,
        adjust: bool = True,
        bias: bool = False,
        min_periods: int = 1,
        ignore_nulls: bool | None = None,
    ) -> Series:
        r"""
        Exponentially-weighted moving standard deviation.

        Parameters
        ----------
        com
            Specify decay in terms of center of mass, :math:`\gamma`, with

                .. math::
                    \alpha = \frac{1}{1 + \gamma} \; \forall \; \gamma \geq 0
        span
            Specify decay in terms of span, :math:`\theta`, with

                .. math::
                    \alpha = \frac{2}{\theta + 1} \; \forall \; \theta \geq 1
        half_life
            Specify decay in terms of half-life, :math:`\lambda`, with

                .. math::
                    \alpha = 1 - \exp \left\{ \frac{ -\ln(2) }{ \lambda } \right\} \;
                    \forall \; \lambda > 0
        alpha
            Specify smoothing factor alpha directly, :math:`0 < \alpha \leq 1`.
        adjust
            Divide by decaying adjustment factor in beginning periods to account for
            imbalance in relative weightings

                - When `adjust=True` (the default) the EW function is calculated
                  using weights :math:`w_i = (1 - \alpha)^i`
                - When `adjust=False` the EW function is calculated
                  recursively by

                  .. math::
                    y_0 &= x_0 \\
                    y_t &= (1 - \alpha)y_{t - 1} + \alpha x_t
        bias
            When `bias=False`, apply a correction to make the estimate statistically
            unbiased.
        min_periods
            Minimum number of observations in window required to have a value
            (otherwise result is null).
        ignore_nulls
            Ignore missing values when calculating weights.

                - When `ignore_nulls=False`, weights are based on absolute
                  positions.
                  For example, the weights of :math:`x_0` and :math:`x_2` used in
                  calculating the final weighted average of
                  [:math:`x_0`, None, :math:`x_2`] are
                  :math:`(1-\alpha)^2` and :math:`1` if `adjust=True`, and
                  :math:`(1-\alpha)^2` and :math:`\alpha` if `adjust=False`.

                - When `ignore_nulls=True` (current default), weights are based
                  on relative positions. For example, the weights of
                  :math:`x_0` and :math:`x_2` used in calculating the final weighted
                  average of [:math:`x_0`, None, :math:`x_2`] are
                  :math:`1-\alpha` and :math:`1` if `adjust=True`,
                  and :math:`1-\alpha` and :math:`\alpha` if `adjust=False`.

        Examples
        --------
        >>> s = pl.Series("a", [1, 2, 3])
        >>> s.ewm_std(com=1, ignore_nulls=False)
        shape: (3,)
        Series: 'a' [f64]
        [
            0.0
            0.707107
            0.963624
        ]
        """

    @deprecate_nonkeyword_arguments(version="0.19.10")
    def ewm_var(
        self,
        com: float | None = None,
        span: float | None = None,
        half_life: float | None = None,
        alpha: float | None = None,
        *,
        adjust: bool = True,
        bias: bool = False,
        min_periods: int = 1,
        ignore_nulls: bool | None = None,
    ) -> Series:
        r"""
        Exponentially-weighted moving variance.

        Parameters
        ----------
        com
            Specify decay in terms of center of mass, :math:`\gamma`, with

                .. math::
                    \alpha = \frac{1}{1 + \gamma} \; \forall \; \gamma \geq 0
        span
            Specify decay in terms of span, :math:`\theta`, with

                .. math::
                    \alpha = \frac{2}{\theta + 1} \; \forall \; \theta \geq 1
        half_life
            Specify decay in terms of half-life, :math:`\lambda`, with

                .. math::
                    \alpha = 1 - \exp \left\{ \frac{ -\ln(2) }{ \lambda } \right\} \;
                    \forall \; \lambda > 0
        alpha
            Specify smoothing factor alpha directly, :math:`0 < \alpha \leq 1`.
        adjust
            Divide by decaying adjustment factor in beginning periods to account for
            imbalance in relative weightings

                - When `adjust=True` (the default) the EW function is calculated
                  using weights :math:`w_i = (1 - \alpha)^i`
                - When `adjust=False` the EW function is calculated
                  recursively by

                  .. math::
                    y_0 &= x_0 \\
                    y_t &= (1 - \alpha)y_{t - 1} + \alpha x_t
        bias
            When `bias=False`, apply a correction to make the estimate statistically
            unbiased.
        min_periods
            Minimum number of observations in window required to have a value
            (otherwise result is null).
        ignore_nulls
            Ignore missing values when calculating weights.

                - When `ignore_nulls=False`, weights are based on absolute
                  positions.
                  For example, the weights of :math:`x_0` and :math:`x_2` used in
                  calculating the final weighted average of
                  [:math:`x_0`, None, :math:`x_2`] are
                  :math:`(1-\alpha)^2` and :math:`1` if `adjust=True`, and
                  :math:`(1-\alpha)^2` and :math:`\alpha` if `adjust=False`.

                - When `ignore_nulls=True` (current default), weights are based
                  on relative positions. For example, the weights of
                  :math:`x_0` and :math:`x_2` used in calculating the final weighted
                  average of [:math:`x_0`, None, :math:`x_2`] are
                  :math:`1-\alpha` and :math:`1` if `adjust=True`,
                  and :math:`1-\alpha` and :math:`\alpha` if `adjust=False`.

        Examples
        --------
        >>> s = pl.Series("a", [1, 2, 3])
        >>> s.ewm_var(com=1, ignore_nulls=False)
        shape: (3,)
        Series: 'a' [f64]
        [
            0.0
            0.5
            0.928571
        ]
        """

    def extend_constant(self, value: IntoExpr, n: int | IntoExprColumn) -> Series:
        """
        Extremely fast method for extending the Series with 'n' copies of a value.

        Parameters
        ----------
        value
            A constant literal value or a unit expressioin with which to extend the
            expression result Series; can pass None to extend with nulls.
        n
            The number of additional values that will be added.

        Examples
        --------
        >>> s = pl.Series([1, 2, 3])
        >>> s.extend_constant(99, n=2)
        shape: (5,)
        Series: '' [i64]
        [
                1
                2
                3
                99
                99
        ]
        """

    def set_sorted(self, *, descending: bool = False) -> Self:
        """
        Flags the Series as 'sorted'.

        Enables downstream code to user fast paths for sorted arrays.

        Parameters
        ----------
        descending
            If the `Series` order is descending.

        Warnings
        --------
        This can lead to incorrect results if this `Series` is not sorted!!
        Use with care!

        Examples
        --------
        >>> s = pl.Series("a", [1, 2, 3])
        >>> s.set_sorted().max()
        3
        """
        return self._from_pyseries(self._s.set_sorted_flag(descending))

    def new_from_index(self, index: int, length: int) -> Self:
        """
        Create a new Series filled with values from the given index.

        Examples
        --------
        >>> s = pl.Series("a", [1, 2, 3, 4, 5])
        >>> s.new_from_index(1,3)
        shape: (3,)
        Series: 'a' [i64]
        [
            2
            2
            2
        ]
        """
        return self._from_pyseries(self._s.new_from_index(index, length))

    def shrink_dtype(self) -> Series:
        """
        Shrink numeric columns to the minimal required datatype.

        Shrink to the dtype needed to fit the extrema of this [`Series`].
        This can be used to reduce memory pressure.

        Examples
        --------
        >>> s = pl.Series("a", [1, 2, 3, 4, 5, 6])
        >>> s
        shape: (6,)
        Series: 'a' [i64]
        [
                1
                2
                3
                4
                5
                6
        ]
        >>> s.shrink_dtype()
        shape: (6,)
        Series: 'a' [i8]
        [
                1
                2
                3
                4
                5
                6
        ]
        """

    def get_chunks(self) -> list[Series]:
        """
        Get the chunks of this Series as a list of Series.

        Examples
        --------
        >>> s1 = pl.Series("a", [1, 2, 3])
        >>> s2 = pl.Series("a", [4, 5, 6])
        >>> s = pl.concat([s1, s2], rechunk = False)
        >>> s.get_chunks()
        [shape: (3,)
        Series: 'a' [i64]
        [
                1
                2
                3
        ], shape: (3,)
        Series: 'a' [i64]
        [
                4
                5
                6
        ]]
        """
        return self._s.get_chunks()

    def implode(self) -> Self:
        """
        Aggregate values into a list.

        Examples
        --------
        >>> s = pl.Series("a", [1, 2, 3])
        >>> s.implode()
        shape: (1,)
        Series: 'a' [list[i64]]
        [
            [1, 2, 3]
        ]
        """

    @deprecate_renamed_function("map_elements", version="0.19.0")
    def apply(
        self,
        function: Callable[[Any], Any],
        return_dtype: PolarsDataType | None = None,
        *,
        skip_nulls: bool = True,
    ) -> Self:
        """
        Apply a custom/user-defined function (UDF) over elements in this Series.

        .. deprecated:: 0.19.0
            This method has been renamed to :func:`Series.map_elements`.

        Parameters
        ----------
        function
            Custom function or lambda.
        return_dtype
            Output datatype. If none is given, the same datatype as this Series will be
            used.
        skip_nulls
            Nulls will be skipped and not passed to the python function.
            This is faster because python can be skipped and because we call
            more specialized functions.
        """
        return self.map_elements(function, return_dtype, skip_nulls=skip_nulls)

    @deprecate_renamed_function("rolling_map", version="0.19.0")
    def rolling_apply(
        self,
        function: Callable[[Series], Any],
        window_size: int,
        weights: list[float] | None = None,
        min_periods: int | None = None,
        *,
        center: bool = False,
    ) -> Series:
        """
        Apply a custom rolling window function.

        .. deprecated:: 0.19.0
            This method has been renamed to :func:`Series.rolling_map`.

        Parameters
        ----------
        function
            Aggregation function
        window_size
            The length of the window.
        weights
            An optional slice with the same length as the window that will be multiplied
            elementwise with the values in the window.
        min_periods
            The number of values in the window that should be non-null before computing
            a result. If None, it will be set equal to:

            - the window size, if `window_size` is a fixed integer
            - 1, if `window_size` is a dynamic temporal size
        center
            Set the labels at the center of the window
        """

    @deprecate_renamed_function("is_first_distinct", version="0.19.3")
    def is_first(self) -> Series:
        """
        Return a boolean mask indicating the first occurrence of each distinct value.

        .. deprecated:: 0.19.3
            This method has been renamed to :func:`Series.is_first_distinct`.

        Returns
        -------
        Series
            Series of data type :class:`Boolean`.
        """

    @deprecate_renamed_function("is_last_distinct", version="0.19.3")
    def is_last(self) -> Series:
        """
        Return a boolean mask indicating the last occurrence of each distinct value.

        .. deprecated:: 0.19.3
            This method has been renamed to :func:`Series.is_last_distinct`.

        Returns
        -------
        Series
            Series of data type :class:`Boolean`.
        """

    @deprecate_function("Use `clip` instead.", version="0.19.12")
    def clip_min(
        self, lower_bound: NumericLiteral | TemporalLiteral | IntoExprColumn
    ) -> Series:
        """
        Clip (limit) the values in an array to a `min` boundary.

        .. deprecated:: 0.19.12
            Use :func:`clip` instead.

        Parameters
        ----------
        lower_bound
            Lower bound.
        """

    @deprecate_function("Use `clip` instead.", version="0.19.12")
    def clip_max(
        self, upper_bound: NumericLiteral | TemporalLiteral | IntoExprColumn
    ) -> Series:
        """
        Clip (limit) the values in an array to a `max` boundary.

        .. deprecated:: 0.19.12
            Use :func:`clip` instead.

        Parameters
        ----------
        upper_bound
            Upper bound.
        """

    @deprecate_function("Use `shift` instead.", version="0.19.12")
    @deprecate_renamed_parameter("periods", "n", version="0.19.11")
    def shift_and_fill(
        self,
        fill_value: int | Expr,
        *,
        n: int = 1,
    ) -> Series:
        """
        Shift values by the given number of places and fill the resulting null values.

        .. deprecated:: 0.19.12
            Use :func:`shift` instead.

        Parameters
        ----------
        fill_value
            Fill None values with the result of this expression.
        n
            Number of places to shift (may be negative).
        """

    @deprecate_function("Use `Series.dtype.is_float()` instead.", version="0.19.13")
    def is_float(self) -> bool:
        """
        Check if this Series has floating point numbers.

        .. deprecated:: 0.19.13
            Use `Series.dtype.is_float()` instead.

        Examples
        --------
        >>> s = pl.Series("a", [1.0, 2.0, 3.0])
        >>> s.is_float()  # doctest: +SKIP
        True
        """
        return self.dtype.is_float()

    @deprecate_function(
        "Use `Series.dtype.is_integer()` instead."
        " For signed/unsigned variants, use `Series.dtype.is_signed_integer()`"
        " or `Series.dtype.is_unsigned_integer()`.",
        version="0.19.13",
    )
    def is_integer(self, signed: bool | None = None) -> bool:
        """
        Check if this Series datatype is an integer (signed or unsigned).

        .. deprecated:: 0.19.13
            Use `Series.dtype.is_integer()` instead.
            For signed/unsigned variants, use `Series.dtype.is_signed_integer()`
            or `Series.dtype.is_unsigned_integer()`.

        Parameters
        ----------
        signed
            * if `None`, both signed and unsigned integer dtypes will match.
            * if `True`, only signed integer dtypes will be considered a match.
            * if `False`, only unsigned integer dtypes will be considered a match.

        Examples
        --------
        >>> s = pl.Series("a", [1, 2, 3], dtype=pl.UInt32)
        >>> s.is_integer()  # doctest: +SKIP
        True
        >>> s.is_integer(signed=False)  # doctest: +SKIP
        True
        >>> s.is_integer(signed=True)  # doctest: +SKIP
        False
        """
        if signed is None:
            return self.dtype.is_integer()
        elif signed is True:
            return self.dtype.is_signed_integer()
        elif signed is False:
            return self.dtype.is_unsigned_integer()

        msg = f"`signed` must be None, True or False; got {signed!r}"
        raise ValueError(msg)

    @deprecate_function("Use `Series.dtype.is_numeric()` instead.", version="0.19.13")
    def is_numeric(self) -> bool:
        """
        Check if this Series datatype is numeric.

        .. deprecated:: 0.19.13
            Use `Series.dtype.is_numeric()` instead.

        Examples
        --------
        >>> s = pl.Series("a", [1, 2, 3])
        >>> s.is_numeric()  # doctest: +SKIP
        True
        """
        return self.dtype.is_numeric()

    @deprecate_function("Use `Series.dtype.is_temporal()` instead.", version="0.19.13")
    def is_temporal(self, excluding: OneOrMoreDataTypes | None = None) -> bool:
        """
        Check if this Series datatype is temporal.

        .. deprecated:: 0.19.13
            Use `Series.dtype.is_temporal()` instead.

        Parameters
        ----------
        excluding
            Optionally exclude one or more temporal dtypes from matching.

        Examples
        --------
        >>> from datetime import date
        >>> s = pl.Series([date(2021, 1, 1), date(2021, 1, 2), date(2021, 1, 3)])
        >>> s.is_temporal()  # doctest: +SKIP
        True
        >>> s.is_temporal(excluding=[pl.Date])  # doctest: +SKIP
        False
        """
        if excluding is not None:
            if not isinstance(excluding, Iterable):
                excluding = [excluding]
            if self.dtype in excluding:
                return False

        return self.dtype.is_temporal()

    @deprecate_function("Use `Series.dtype == pl.Boolean` instead.", version="0.19.14")
    def is_boolean(self) -> bool:
        """
        Check if this Series is a Boolean.

        .. deprecated:: 0.19.14
            Use `Series.dtype == pl.Boolean` instead.

        Examples
        --------
        >>> s = pl.Series("a", [True, False, True])
        >>> s.is_boolean()  # doctest: +SKIP
        True
        """
        return self.dtype == Boolean

    @deprecate_function("Use `Series.dtype == pl.String` instead.", version="0.19.14")
    def is_utf8(self) -> bool:
        """
        Check if this Series datatype is a String.

        .. deprecated:: 0.19.14
            Use `Series.dtype == pl.String` instead.

        Examples
        --------
        >>> s = pl.Series("x", ["a", "b", "c"])
        >>> s.is_utf8()  # doctest: +SKIP
        True
        """
        return self.dtype == String

    @deprecate_renamed_function("gather_every", version="0.19.14")
    def take_every(self, n: int, offset: int = 0) -> Series:
        """
        Take every nth value in the Series and return as new Series.

        .. deprecated:: 0.19.14
            This method has been renamed to :meth:`gather_every`.

        Parameters
        ----------
        n
            Gather every *n*-th row.
        offset
            Starting index.
        """
        return self.gather_every(n, offset)

    @deprecate_renamed_function("gather", version="0.19.14")
    def take(
        self, indices: int | list[int] | Expr | Series | np.ndarray[Any, Any]
    ) -> Series:
        """
        Take values by index.

        .. deprecated:: 0.19.14
            This method has been renamed to :meth:`gather`.

        Parameters
        ----------
        indices
            Index location used for selection.
        """
        return self.gather(indices)

    @deprecate_renamed_function("scatter", version="0.19.14")
    @deprecate_renamed_parameter("idx", "indices", version="0.19.14")
    @deprecate_renamed_parameter("value", "values", version="0.19.14")
    def set_at_idx(
        self,
        indices: Series | np.ndarray[Any, Any] | Sequence[int] | int,
        values: (
            int
            | float
            | str
            | bool
            | date
            | datetime
            | Sequence[int]
            | Sequence[float]
            | Sequence[bool]
            | Sequence[str]
            | Sequence[date]
            | Sequence[datetime]
            | Series
            | None
        ),
    ) -> Series:
        """
        Set values at the index locations.

        .. deprecated:: 0.19.14
            This method has been renamed to :meth:`scatter`.

        Parameters
        ----------
        indices
            Integers representing the index locations.
        values
            Replacement values.
        """
        return self.scatter(indices, values)

    @deprecate_renamed_function("cum_sum", version="0.19.14")
    def cumsum(self, *, reverse: bool = False) -> Series:
        """
        Get an array with the cumulative sum computed at every element.

        .. deprecated:: 0.19.14
            This method has been renamed to :meth:`cum_sum`.

        Parameters
        ----------
        reverse
            reverse the operation.
        """
        return self.cum_sum(reverse=reverse)

    @deprecate_renamed_function("cum_max", version="0.19.14")
    def cummax(self, *, reverse: bool = False) -> Series:
        """
        Get an array with the cumulative max computed at every element.

        .. deprecated:: 0.19.14
            This method has been renamed to :meth:`cum_max`.

        Parameters
        ----------
        reverse
            reverse the operation.
        """
        return self.cum_max(reverse=reverse)

    @deprecate_renamed_function("cum_min", version="0.19.14")
    def cummin(self, *, reverse: bool = False) -> Series:
        """
        Get an array with the cumulative min computed at every element.

        .. deprecated:: 0.19.14
            This method has been renamed to :meth:`cum_min`.

        Parameters
        ----------
        reverse
            reverse the operation.
        """
        return self.cum_min(reverse=reverse)

    @deprecate_renamed_function("cum_prod", version="0.19.14")
    def cumprod(self, *, reverse: bool = False) -> Series:
        """
        Get an array with the cumulative product computed at every element.

        .. deprecated:: 0.19.14
            This method has been renamed to :meth:`cum_prod`.

        Parameters
        ----------
        reverse
            reverse the operation.
        """
        return self.cum_prod(reverse=reverse)

    @deprecate_function(
        "Use `Series.to_numpy(allow_copy=False) instead.", version="0.19.14"
    )
    def view(self, *, ignore_nulls: bool = False) -> SeriesView:
        """
        Get a view into this Series data with a numpy array.

        .. deprecated:: 0.19.14
            This method will be removed in a future version.

        This operation doesn't clone data, but does not include missing values.
        Don't use this unless you know what you are doing.

        Parameters
        ----------
        ignore_nulls
            If True then nulls are converted to 0.
            If False then an Exception is raised if nulls are present.
        """
        if not ignore_nulls:
            assert not self.null_count()

        from polars.series._numpy import SeriesView, _ptr_to_numpy

        ptr_type = dtype_to_ctype(self.dtype)
        ptr = self._s.as_single_ptr()
        array = _ptr_to_numpy(ptr, self.len(), ptr_type)
        array.setflags(write=False)
        return SeriesView(array, self)

    @deprecate_function(
        "It has been renamed to `replace`."
        " The default behavior has changed to keep any values not present in the mapping unchanged."
        " Pass `default=None` to keep existing behavior.",
        version="0.19.16",
    )
    @deprecate_renamed_parameter("remapping", "mapping", version="0.19.16")
    def map_dict(
        self,
        mapping: dict[Any, Any],
        *,
        default: Any = None,
        return_dtype: PolarsDataType | None = None,
    ) -> Self:
        """
        Replace values in the Series using a remapping dictionary.

        .. deprecated:: 0.19.16
            This method has been renamed to :meth:`replace`. The default behavior
            has changed to keep any values not present in the mapping unchanged.
            Pass `default=None` to keep existing behavior.

        Parameters
        ----------
        mapping
            Dictionary containing the before/after values to map.
        default
            Value to use when the remapping dict does not contain the lookup value.
            Use `pl.first()`, to keep the original value.
        return_dtype
            Set return dtype to override automatic return dtype determination.
        """
        return self.replace(mapping, default=default, return_dtype=return_dtype)

    @deprecate_renamed_function("equals", version="0.19.16")
    def series_equal(
        self, other: Series, *, null_equal: bool = True, strict: bool = False
    ) -> bool:
        """
        Check whether the Series is equal to another Series.

        .. deprecated:: 0.19.16
            This method has been renamed to :meth:`equals`.

        Parameters
        ----------
        other
            Series to compare with.
        null_equal
            Consider null values as equal.
        strict
            Don't allow different numerical dtypes, e.g. comparing `pl.UInt32` with a
            `pl.Int64` will return `False`.
        """
        return self.equals(other, null_equal=null_equal, strict=strict)

    # Keep the `list` and `str` properties below at the end of the definition of Series,
    # as to not confuse mypy with the type annotation `str` and `list`

    @property
    def bin(self) -> BinaryNameSpace:
        """Create an object namespace of all binary related methods."""
        return BinaryNameSpace(self)

    @property
    def cat(self) -> CatNameSpace:
        """Create an object namespace of all categorical related methods."""
        return CatNameSpace(self)

    @property
    def dt(self) -> DateTimeNameSpace:
        """Create an object namespace of all datetime related methods."""
        return DateTimeNameSpace(self)

    @property
    def list(self) -> ListNameSpace:
        """Create an object namespace of all list related methods."""
        return ListNameSpace(self)

    @property
    def arr(self) -> ArrayNameSpace:
        """Create an object namespace of all array related methods."""
        return ArrayNameSpace(self)

    @property
    def str(self) -> StringNameSpace:
        """Create an object namespace of all string related methods."""
        return StringNameSpace(self)

    @property
    def struct(self) -> StructNameSpace:
        """Create an object namespace of all struct related methods."""
        return StructNameSpace(self)

    @property
    def plot(self) -> hvPlotTabularPolars:
        """
        Create a plot namespace.

        Polars does not implement plotting logic itself, but instead defers to
        hvplot. Please see the `hvplot reference gallery <https://hvplot.holoviz.org/reference/index.html>`_
        for more information and documentation.

        Examples
        --------
        Histogram:

        >>> s = pl.Series("values", [1, 4, 2])
        >>> s.plot.hist()  # doctest: +SKIP

        KDE plot (note: in addition to ``hvplot``, this one also requires ``scipy``):

        >>> s.plot.kde()  # doctest: +SKIP

        For more info on what you can pass, you can use ``hvplot.help``:

        >>> import hvplot  # doctest: +SKIP
        >>> hvplot.help("hist")  # doctest: +SKIP
        """
        if not _HVPLOT_AVAILABLE or parse_version(hvplot.__version__) < parse_version(
            "0.9.1"
        ):
            msg = "hvplot>=0.9.1 is required for `.plot`"
            raise ModuleUpgradeRequired(msg)
        hvplot.post_patch()
        return hvplot.plotting.core.hvPlotTabularPolars(self)


def _resolve_temporal_dtype(
    dtype: PolarsDataType | None,
    ndtype: np.dtype[np.datetime64] | np.dtype[np.timedelta64],
) -> PolarsDataType | None:
    """Given polars/numpy temporal dtypes, resolve to an explicit unit."""
    PolarsType = Duration if ndtype.type == np.timedelta64 else Datetime
    if dtype is None or (dtype == Datetime and not getattr(dtype, "time_unit", None)):
        time_unit = getattr(dtype, "time_unit", None) or np.datetime_data(ndtype)[0]
        # explicit formulation is verbose, but keeps mypy happy
        # (and avoids unsupported timeunits such as "s")
        if time_unit == "ns":
            dtype = PolarsType("ns")
        elif time_unit == "us":
            dtype = PolarsType("us")
        elif time_unit == "ms":
            dtype = PolarsType("ms")
        elif time_unit == "D" and ndtype.type == np.datetime64:
            dtype = Date
    return dtype
