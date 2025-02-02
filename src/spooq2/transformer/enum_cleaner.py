import sys
import pyspark.sql.functions as F, types as T
from pyspark.sql.column import Column

from .transformer import Transformer


class EnumCleaner(Transformer):
    """
    Cleanses a dataframe based on lists of allowed|disallowed values.

    Example
    -------
    >>> transformer = EnumCleaner(
    >>>     cleaning_definitions={
    >>>         "status": {
    >>>             "elements": ["active", "inactive"],
    >>>         },
    >>>         "version": {
    >>>             "elements": ["", "None", "none", "null", "NULL"],
    >>>             "mode": "disallow",
    >>>             "default": None
    >>>         },
    >>>     }
    >>> )

    Parameters
    ----------
    cleaning_definitions : :py:class:`dict`
        Dictionary containing column names and respective cleansing rules


    Note
    ----
    Following cleansing rule attributes per column are supported:

        * elements, mandatory - :class:`list`
            A list of elements which will be used to allow or reject (based on mode) values from the input DataFrame.
        * mode, allow|disallow, defaults to 'allow' - :any:`str`
            "allow" will set all values which are NOT in the list (ignoring NULL) to the default value.
            "disallow" will set all values which ARE in the list (ignoring NULL) to the default value.
        * default, defaults to None - :class:`~pyspark.sql.column.Column` or any primitive Python value
            If a value gets cleansed it gets replaced with the provided default value.

    Returns
    -------
    :any:`pyspark.sql.DataFrame`
        The transformed DataFrame

    Raises
    ------
    :any:`exceptions.ValueError`
        Enumeration-based cleaning requires a non-empty list of elements per cleaning rule!
        Spooq did not find such a list for column: {column_name}

    :any:`exceptions.ValueError`
        Only the following modes are supported by EnumCleaner: 'allow' and 'disallow'.

    Warning
    -------
    None values are explicitly ignored as input values because `F.lit(None).isin(["elem1", "elem2"])` will neither
    return True nor False but None.
    If you want to replace Null values you should use the method ~pyspark.sql.DataFrame.fillna from Spark.
    """

    def __init__(self, cleaning_definitions={}):
        super().__init__()
        self.cleaning_definitions = cleaning_definitions
        self.logger.debug("Enumeration List: " + str(self.cleaning_definitions))

    def transform(self, input_df):
        self.logger.debug("input_df Schema: " + input_df._jdf.schema().treeString())

        for column_name, cleaning_definition in list(self.cleaning_definitions.items()):
            self.logger.debug(f"Cleaning Definition for Column {column_name}: {str(cleaning_definition)}")
            elements = cleaning_definition.get("elements", None)
            if not elements:
                raise ValueError(
                    f"Enumeration-based cleaning requires a non-empty list of elements per cleaning rule!",
                    f"\nSpooq did not find such a list for column: {column_name}"
                )
            mode = cleaning_definition.get("mode", "allow")
            substitute = cleaning_definition.get("default", None)
            data_type = input_df.schema[column_name].dataType
            if not isinstance(substitute, Column):
                substitute = F.lit(substitute)

            if mode == "allow":
                input_df = input_df.withColumn(
                    column_name,
                    F.when(F.col(column_name).isNull(), F.lit(None))
                    .otherwise(
                        F.when(F.col(column_name).isin(elements), F.col(column_name))
                        .otherwise(substitute)
                    )
                    .cast(data_type)
                )
            elif mode == "disallow":
                input_df = input_df.withColumn(
                    column_name,
                    F.when(F.col(column_name).isNull(), F.lit(None))
                    .otherwise(
                        F.when(F.col(column_name).isin(elements), substitute)
                        .otherwise(F.col(column_name))
                    )
                    .cast(data_type)
                )
            else:
                raise ValueError(
                    f"Only the following modes are supported by EnumCleaner: 'allow' and 'disallow'."
                )

        return input_df
