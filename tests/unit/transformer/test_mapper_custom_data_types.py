from builtins import object
import json
import pytest
import datetime
from pyspark.sql import functions as F  # noqa: N812
from pyspark.sql import Row
from pyspark.sql import types as T

import spooq2.transformer.mapper_custom_data_types as custom_types
from spooq2.transformer import Mapper


def parameter_to_string_id(val):
    return "<" + str(val) + ">"


def get_input_df(spark_session, spark_context, source_key, input_value):
    input_json = json.dumps(
        {"attributes": {
            "data": {
                source_key: input_value
            }
        }})
    return spark_session.read.json(spark_context.parallelize([input_json]))


class TestDynamicallyCallMethodsByDataTypeName(object):
    # fmt: off
    @pytest.mark.parametrize(("function_name", "data_type"), [
        ("_generate_select_expression_for_as_is",                        "as_is"),
        ("_generate_select_expression_without_casting",                  "as_is"),
        ("_generate_select_expression_without_casting",                  "keep"),
        ("_generate_select_expression_without_casting",                  "no_change"),
        ("_generate_select_expression_for_json_string",                  "json_string"),
        ("_generate_select_expression_for_timestamp_ms_to_ms",           "timestamp_ms_to_ms"),
        ("_generate_select_expression_for_timestamp_ms_to_s",            "timestamp_ms_to_s"),
        ("_generate_select_expression_for_timestamp_s_to_ms",            "timestamp_s_to_ms"),
        ("_generate_select_expression_for_timestamp_s_to_ms",            "timestamp_s_to_ms"),
        ("_generate_select_expression_for_StringNull",                   "StringNull"),
        ("_generate_select_expression_for_IntNull",                      "IntNull"),
        ("_generate_select_expression_for_IntBoolean",                   "IntBoolean"),
        ("_generate_select_expression_for_StringBoolean",                "StringBoolean"),
        ("_generate_select_expression_for_TimestampMonth",               "TimestampMonth"),
        ("_generate_select_expression_for_extended_string_to_timestamp", "extended_string_to_timestamp"),
    ])
    # fmt: on
    def test_get_select_expression_for_custom_type(self, data_type, function_name, mocker):
        source_column, name = "element.key", "element_key"
        mocked_function = mocker.patch.object(custom_types, function_name)
        custom_types._get_select_expression_for_custom_type(source_column, name, data_type)

        mocked_function.assert_called_once_with(source_column, name)

    def test_exception_is_raised_if_data_type_not_found(self):
        source_column, name = "element.key", "element_key"
        data_type = "NowhereToBeFound"

        with pytest.raises(AttributeError):
            custom_types._get_select_expression_for_custom_type(
                source_column, name, data_type)

# fmt: off
@pytest.mark.parametrize(("input_value", "value"), [
    ("only some text",
     "only some text"),
    (None,
     None),
    ({"key": "value"},
     Row(key="value")),
    ({"key": {"other_key": "value"}},
     Row(key=Row(other_key="value"))),
    ({"age": 18,"weight": 75},
     Row(age=18, weight=75)),
    ({"list_of_friend_ids": [12, 75, 44, 76]},
     Row(list_of_friend_ids=[12, 75, 44, 76])),
    ([{"weight": "75"}, {"weight": "76"}, {"weight": "73"}],
     [Row(weight="75"), Row(weight="76"), Row(weight="73")]),
    ({"list_of_friend_ids": [{"id": 12}, {"id": 75}, {"id": 44}, {"id": 76}]},
     Row(list_of_friend_ids=[Row(id=12), Row(id=75), Row(id=44), Row(id=76)])),
])
# fmt: on
def test_generate_select_expression_without_casting(input_value, value,
                                                    spark_session,
                                                    spark_context):
    source_key, name = "demographics", "statistics"
    input_df = get_input_df(spark_session, spark_context, source_key,
                            input_value)
    result_column = custom_types._generate_select_expression_without_casting(
        source_column=input_df["attributes"]["data"][source_key], name=name)
    output_df = input_df.select(result_column)
    assert output_df.schema.fieldNames() == [name], "Renaming of column"
    assert output_df.first()[name] == value, "Processing of column value"

# fmt: off
@pytest.mark.parametrize(("input_value", "value"), [
    ("only some text",
    "only some text"),
    (None,
     None),
    ({"key": "value"},
     '{"key": "value"}'),
    ({"key": {"other_key": "value"}},
     '{"key": {"other_key": "value"}}'),
    ({"age": 18, "weight": 75},
     '{"age": 18, "weight": 75}'),
    ({"list_of_friend_ids": [12, 75, 44, 76]},
     '{"list_of_friend_ids": [12, 75, 44, 76]}'),
    ([{"weight": "75"}, {"weight": "76"}, {"weight": "73"}],
     '[{"weight": "75"}, {"weight": "76"}, {"weight": "73"}]'),
    ({"list_of_friend_ids": [{"id": 12}, {"id": 75}, {"id": 44}, {"id": 76}]},
     '{"list_of_friend_ids": [{"id": 12}, {"id": 75}, {"id": 44}, {"id": 76}]}')
])
# fmt: on
def test_generate_select_expression_for_json_string(input_value, value,
                                                    spark_session,
                                                    spark_context):
    source_key, name = "demographics", "statistics"
    input_df = get_input_df(spark_session, spark_context, source_key,
                            input_value)
    result_column = custom_types._generate_select_expression_for_json_string(
        source_column=input_df["attributes"]["data"][source_key], name=name)
    output_df = input_df.select(result_column)
    assert output_df.schema.fieldNames() == [name], "Renaming of column"
    assert output_df.schema[name].dataType.typeName(
    ) == "string", "Casting of column"
    assert output_df.first()[name] == value, "Processing of column value"


class TestConversionsFromString(object):

    # fmt:off
    @pytest.mark.parametrize(
        argnames=("input_value", "expected_value"),
        argvalues=[
            ("123456",        123456),
            ("-123456",      -123456),
            ("-1",                -1),
            ("0",                  0),
            ("NULL",            None),
            ("null",            None),
            ("None",            None),
            (None,              None),
            ("Hello World",     None),
            ("2020-08-12",      None),
            (None,              None),
            ("1234.56",         1234),
            ("-1234.56",       -1234),
            ("123,456",         None),  # commas not allowed due to their ambiguity
            ("-123,456",        None),  # commas not allowed due to their ambiguity
            ("123_456",       123456),
            ("-123_456",     -123456),
            ("   123456",     123456),
            ("123456   ",     123456),
            (" 123456  ",     123456),
        ])
    # fmt:on
    def test_extended_string_to_int(self, spark_session, input_value, expected_value):
        input_df = spark_session.createDataFrame(
            [Row(input_key=input_value)],
            schema=T.StructType([T.StructField("input_key", T.StringType(), True)]))
        output_df = Mapper(mapping=[("output_key", "input_key", "extended_string_to_int")]).transform(input_df)
        assert output_df.first().output_key == expected_value
        assert isinstance(output_df.schema["output_key"].dataType, T.IntegerType)


    # fmt:off
    @pytest.mark.parametrize(
        argnames=("input_value", "expected_value"),
        argvalues=[
            ("21474836470",                21474836470),
            ("-21474836470",              -21474836470),
            ("-1",                                  -1),
            ("0",                                    0),
            ("NULL",                              None),
            ("null",                              None),
            ("None",                              None),
            (None,                                None),
            ("Hello World",                       None),
            ("2020-08-12T12:43:14+0000",          None),
            ("214748364.70",                 214748364),
            ("-214748364.70",               -214748364),
            ("21,474,836,470",                    None),  # commas not allowed due to their ambiguity
            ("-21,474,836,470",                   None),  # commas not allowed due to their ambiguity
            ("214748364,7",                       None),  # commas not allowed due to their ambiguity
            ("-214748364,7",                      None),  # commas not allowed due to their ambiguity
            ("21_474_836_470",             21474836470),
            ("-21_474_836_470",           -21474836470),
            ("   21474836470",             21474836470),
            ("21474836470   ",             21474836470),
            (" 21474836470  ",             21474836470),
        ])
    # fmt:on
    def test_extended_string_to_long(self, spark_session, input_value, expected_value):
        input_df = spark_session.createDataFrame(
            [Row(input_key=input_value)],
            schema=T.StructType([T.StructField("input_key", T.StringType(), True)]))
        output_df = Mapper(mapping=[("output_key", "input_key", "extended_string_to_long")]).transform(input_df)
        assert output_df.first().output_key == expected_value
        assert isinstance(output_df.schema["output_key"].dataType, T.LongType)

    # fmt:off
    @pytest.mark.parametrize(
        argnames=("input_value", "expected_value"),
        argvalues=[
            ("123456.0",      123456.0),
            ("-123456.0",    -123456.0),
            ("-1.0",              -1.0),
            ("0.0",                0.0),
            ("NULL",              None),
            ("null",              None),
            ("None",              None),
            (None,                None),
            ("1234.56",        1234.56),
            ("-1234.56",      -1234.56),
            ("-123,456.7",        None),  # commas not allowed due to their ambiguity
            ("123,456.7",         None),  # commas not allowed due to their ambiguity
            ("-123456,7",         None),  # commas not allowed due to their ambiguity
            ("123456,7",          None),  # commas not allowed due to their ambiguity
            ("123_456.7",     123456.7),
            ("-123_456.7",   -123456.7),
            ("   123456.7",   123456.7),
            ("123456.7   ",   123456.7),
            (" 123456.7  ",   123456.7),
        ])
    # fmt:on
    def test_extended_string_to_float(self, spark_session, input_value, expected_value):
        input_df = spark_session.createDataFrame(
            [Row(input_key=input_value)],
            schema=T.StructType([T.StructField("input_key", T.StringType(), True)]))
        output_df = Mapper(mapping=[("output_key", "input_key", "extended_string_to_float")]).transform(input_df)
        actual_value = output_df.first().output_key
        if actual_value is not None:
            assert pytest.approx(actual_value) == expected_value
        else:
            assert actual_value == expected_value
        assert isinstance(output_df.schema["output_key"].dataType, T.FloatType)

    # fmt:off
    @pytest.mark.parametrize(
        argnames=("input_value", "expected_value"),
        argvalues=[
            ("214748364.70",          214748364.70),
            ("-214748364.70",        -214748364.70),
            ("-1.0",                          -1.0),
            ("0.0",                            0.0),
            ("NULL",                          None),
            ("null",                          None),
            ("None",                          None),
            (None,                            None),
            ("21474836470",          21474836470.0),
            ("-21474836470",        -21474836470.0),
            ("21,474,836,470.7",              None),  # commas not allowed due to their ambiguity
            ("-21,474,836,470.7",             None),  # commas not allowed due to their ambiguity
            ("21474836470,7",                 None),  # commas not allowed due to their ambiguity
            ("-21474836470,7",                None),  # commas not allowed due to their ambiguity
            ("21_474_836_470.7",     21474836470.7),
            ("-21_474_836_470.7",   -21474836470.7),
            ("   21474836470.7",     21474836470.7),
            ("21474836470.7   ",     21474836470.7),
            (  " 21474836470.7  ",   21474836470.7),
        ])
    # fmt:on
    def test_extended_string_to_double(self, spark_session, input_value, expected_value):
        input_df = spark_session.createDataFrame(
            [Row(input_key=input_value)],
            schema=T.StructType([T.StructField("input_key", T.StringType(), True)]))
        output_df = Mapper(mapping=[("output_key", "input_key", "extended_string_to_double")]).transform(input_df)
        actual_value = output_df.first().output_key
        if actual_value is not None:
            assert pytest.approx(actual_value) == expected_value
        else:
            assert actual_value == expected_value
        assert isinstance(output_df.schema["output_key"].dataType, T.DoubleType)

    # fmt:off
    @pytest.mark.parametrize(
        argnames=("input_value", "expected_value"),
        argvalues=[
            ("1",       True),
            ("TRUE",    True),
            ("True",    True),
            ("true",    True),
            ("0",       False),
            ("-1",      None),
            ("123",     None),
            ("-123",    None),
            ("FALSE",   False),
            ("False",   False),
            ("false",   False),
            ("n",       False),
            ("no",      False),
            ("yes",     True),
            ("y",       True),
            ("   true", True),
            ("true   ", True),
            (" true  ", True),
        ])
    # fmt:on
    def test_extended_string_to_boolean(self, spark_session, input_value, expected_value):
        input_df = spark_session.createDataFrame(
            [Row(input_key=input_value)],
            schema=T.StructType([T.StructField("input_key", T.StringType(), True)]))
        output_df = Mapper(mapping=[("output_key", "input_key", "extended_string_to_boolean")]).transform(input_df)
        assert output_df.first().output_key == expected_value
        assert isinstance(output_df.schema["output_key"].dataType, T.BooleanType)

    # fmt:off
    @pytest.mark.parametrize(
        argnames=("input_value", "expected_value"),
        argvalues=[
            ("2020-08-12T12:43:14+0000",   datetime.datetime(2020, 8, 12, 12, 43, 14)),
            ("2020-08-12T12:43:14+00:00",  datetime.datetime(2020, 8, 12, 12, 43, 14)),
            ("2020-08-12T12:43:14Z00:00",  datetime.datetime(2020, 8, 12, 12, 43, 14)),
            ("2020-08-12T12:43:14Z0000",   datetime.datetime(2020, 8, 12, 12, 43, 14)),
            ("  2020-08-12T12:43:14+0000", datetime.datetime(2020, 8, 12, 12, 43, 14)),
            ("2020-08-12T12:43:14+0000  ", datetime.datetime(2020, 8, 12, 12, 43, 14)),
            (" 2020-08-12T12:43:14+0000 ", datetime.datetime(2020, 8, 12, 12, 43, 14)),
            ("2020-08-12T12:43:14+02:00",  datetime.datetime(2020, 8, 12, 10, 43, 14)),
            ("2020-08-12T12:43:14+0200",   None),  # only `+HH:MM` is supported by Spark for timezone offsets
            ("2020-08-12T12:43:14Z0200",   None),  # only `+HH:MM` is supported by Spark for timezone offsets
            ("2020-08-12T12:43:14",        datetime.datetime(2020, 8, 12, 12, 43, 14)),
            ("2020-08-12 12:43:14",        datetime.datetime(2020, 8, 12, 12, 43, 14)),
            ("2020-08-12",                 datetime.datetime(2020, 8, 12, 0, 0, 0)),
            ("1597069446",                 datetime.datetime(2020, 8, 10, 14, 24, 6)),
            ("-1597069446",                datetime.datetime(1919, 5, 24, 9, 35, 54)),
            ("1597069446000",              "out_of_range_for_python"),  # Spark can handle it but not Python
            ("-1597069446000",             "out_of_range_for_python"),  # Spark can handle it but not Python
            ("null",                       None),
            ("0",                          datetime.datetime(1970, 1, 1, 0, 0, 0)),
            ("-1",                         datetime.datetime(1969, 12, 31, 23, 59, 59)),
            ("1",                          datetime.datetime(1970, 1, 1, 0, 0, 1)),
            ("nil",                        None),
        ],
        ids=parameter_to_string_id
    )
    # fmt:on
    def test_extended_string_to_timestamp(self, spark_session, input_value, expected_value):
        # test uses timezone set to GMT / UTC (pytest.ini)!
        input_df = spark_session.createDataFrame(
            [Row(input_key=input_value)],
            schema=T.StructType([T.StructField("input_key", T.StringType(), True)]))
        output_df = Mapper(mapping=[("output_key", "input_key", "extended_string_to_timestamp")]).transform(input_df)
        # workaround via pandas necessary due to bug with direct conversion
        # to python datetime wrt timezone conversions (https://issues.apache.org/jira/browse/SPARK-32123)
        try:
            output_pd_df = output_df.toPandas()
            actual_value = output_pd_df.iloc[0]["output_key"].to_pydatetime()
        except ValueError:
            # If input is in milliseconds it will still be stored in the DF but cannot be collected in Python
            actual_value = "out_of_range_for_python"
        except AttributeError:
            # `.to_pydatetime()` can only be used on datetimes and throws AttributeErrors on other objects / None
            actual_value = None
        assert actual_value == expected_value
        assert isinstance(output_df.schema["output_key"].dataType, T.TimestampType)


class TestAnonymizingMethods(object):
    # fmt: off
    @pytest.mark.parametrize(("input_value", "value"), [
        ("my_first_mail@myspace.com", "1"),
        ("",                          None),
        (None,                        None),
        (" ",                         "1"),
        (100,                         "1"),
        (0,                           "1")],
    )
    # fmt: on
    def test_generate_select_expression_for_StringBoolean(
            self, input_value, value, spark_session, spark_context):
        source_key, name = "email_address", "mail"
        input_df = get_input_df(spark_session, spark_context, source_key,
                                input_value)
        result_column = custom_types._generate_select_expression_for_StringBoolean(
            source_column=input_df["attributes"]["data"][source_key],
            name=name)
        output_df = input_df.select(result_column)

        assert output_df.schema.fieldNames() == [name], "Renaming of column"
        assert output_df.schema[name].dataType.typeName(
        ) == "string", "Casting of column"
        assert output_df.first()[name] == value, "Processing of column value"

    # fmt: off
    @pytest.mark.parametrize(("input_value", "value"), [
        ("my_first_mail@myspace.com", None),
        ("",                          None),
        (None,                        None),
        (" ",                         None),
        (100,                         None),
        (0,                           None)],
    )
    # fmt: on
    def test_generate_select_expression_for_StringNull(self, input_value,
                                                       value, spark_session,
                                                       spark_context):
        source_key, name = "email_address", "mail"
        input_df = get_input_df(spark_session, spark_context, source_key,
                                input_value)
        result_column = custom_types._generate_select_expression_for_StringNull(
            source_column=input_df["attributes"]["data"][source_key],
            name=name)
        output_df = input_df.select(result_column)

        assert output_df.schema.fieldNames() == [name], "Renaming of column"
        assert output_df.schema[name].dataType.typeName(
        ) == "string", "Casting of column"
        assert output_df.first()[name] == value, "Processing of column value"

    # fmt: off
    @pytest.mark.parametrize(("input_value", "value"), [
        (12345,             1),
        ("",                1),
        ("some text",       1),
        (None,              None),
        (0,                 1),
        (1,                 1),
        (-1,                1),
        (5445.23,           1),
        (float("inf"),      1),
        (-1 * float("inf"), 1)
    ])
    # fmt: on
    def test_generate_select_expression_for_IntBoolean(self, input_value,
                                                       value, spark_session,
                                                       spark_context):
        source_key, name = "user_id", "id"
        input_df = get_input_df(spark_session, spark_context, source_key,
                                input_value)
        result_column = custom_types._generate_select_expression_for_IntBoolean(
            source_column=input_df["attributes"]["data"][source_key],
            name=name)
        output_df = input_df.select(result_column)

        assert output_df.schema.fieldNames() == [name], "Renaming of column"
        assert output_df.schema[name].dataType.typeName(
        ) == "integer", "Casting of column"
        assert output_df.first()[name] == value, "Processing of column value"

    # fmt: off
    @pytest.mark.parametrize(("input_value", "value"), [
        (12345,             None),
        ("",                None),
        ("some text",       None),
        (None,              None),
        (0,                 None),
        (1,                 None),
        (-1,                None),
        (5445.23,           None),
        (float("inf"),      None),
        (-1 * float("inf"), None),
    ])
    # fmt: on
    def test_generate_select_expression_for_IntNull(self, input_value, value,
                                                    spark_session,
                                                    spark_context):
        source_key, name = "user_id", "id"
        input_df = get_input_df(spark_session, spark_context, source_key,
                                input_value)
        result_column = custom_types._generate_select_expression_for_IntNull(
            source_column=input_df["attributes"]["data"][source_key],
            name=name)
        output_df = input_df.select(result_column)

        assert output_df.schema.fieldNames() == [name], "Renaming of column"
        assert output_df.schema[name].dataType.typeName(
        ) == "integer", "Casting of column"
        assert output_df.first()[name] == value, "Processing of column value"

    # fmt: off
    @pytest.mark.parametrize(("input_value", "value"), [
        (None,         None),
        ("1955-09-41", None),
        ("1969-04-03", "1969-04-01"),
        ("1985-03-07", "1985-03-01"),
        ("1998-06-10", "1998-06-01"),
        ("1967-05-16", "1967-05-01"),
        ("1953-01-01", "1953-01-01"),
        ("1954-11-06", "1954-11-01"),
        ("1978-09-05", "1978-09-01"),
        ("1999-05-23", "1999-05-01"),
    ])
    # fmt: on
    def test_generate_select_expression_for_TimestampMonth(
            self, input_value, value, spark_session, spark_context):
        source_key, name = "day_of_birth", "birthday"
        input_df = get_input_df(spark_session, spark_context, source_key, input_value)
        input_df = input_df.withColumn(
            source_key,
            F.to_utc_timestamp(input_df["attributes"]["data"][source_key],
                               "yyyy-MM-dd"))
        result_column = custom_types._generate_select_expression_for_TimestampMonth(
            source_column=input_df[source_key], name=name)
        output_df = input_df.select(result_column)

        assert output_df.schema.fieldNames() == [name], "Renaming of column"
        assert output_df.schema[name].dataType.typeName(
        ) == "timestamp", "Casting of column"
        output_value = output_df.first()[name]
        if output_value:
            output_value = datetime.date.strftime(output_value,
                                                  format("%Y-%m-%d"))
        else:
            output_value = None
        assert output_value == value, "Processing of column value"


class TestTimestampMethods(object):
    # fmt: off
    @pytest.mark.parametrize(("input_value", "value"), [
        (0,              0),              # minimum valid timestamp
        (-1,             None),           # minimum valid timestamp - 1 ms
        (None,           None),
        (4102358400000,  4102358400000),  # maximum valid timestamp
        (4102358400001,  None),           # maximum valid timestamp + 1 ms
        (5049688276000,  None),
        (3469296996000,  3469296996000),
        (7405162940000,  None),
        (2769601503000,  2769601503000),
        (-1429593275000, None),
        (3412549669000,  3412549669000),
    ])
    # fmt: on
    def test_generate_select_expression_for_timestamp_ms_to_ms(
            self, input_value, value, spark_session, spark_context):
        source_key, name = "updated_at", "updated_at_ms"
        input_df = get_input_df(spark_session, spark_context, source_key,
                                input_value)
        result_column = custom_types._generate_select_expression_for_timestamp_ms_to_ms(
            source_column=input_df["attributes"]["data"][source_key],
            name=name)
        output_df = input_df.select(result_column)

        assert output_df.schema.fieldNames() == [name], "Renaming of column"
        assert output_df.schema[name].dataType.typeName(
        ) == "long", "Casting of column"
        assert output_df.first()[name] == value, "Processing of column value"

    # fmt: off
    @pytest.mark.parametrize(("input_value", "value"), [
        (0,              0),           # minimum valid timestamp
        (-1,             None),        # minimum valid timestamp - 1 ms
        (None,           None),
        (4102358400000,  4102358400),  # maximum valid timestamp
        (4102358400001,  None),        # maximum valid timestamp + 1 ms
        (5049688276000,  None),
        (3469296996000,  3469296996),
        (7405162940000,  None),
        (2769601503000,  2769601503),
        (-1429593275000, None),
        (3412549669000,  3412549669),
    ])
    # fmt: on
    def test_generate_select_expression_for_timestamp_ms_to_s(
            self, input_value, value, spark_session, spark_context):
        source_key, name = "updated_at", "updated_at_ms"
        input_df = get_input_df(spark_session, spark_context, source_key,
                                input_value)
        result_column = custom_types._generate_select_expression_for_timestamp_ms_to_s(
            source_column=input_df["attributes"]["data"][source_key],
            name=name)
        output_df = input_df.select(result_column)

        assert output_df.schema.fieldNames() == [name], "Renaming of column"
        assert output_df.schema[name].dataType.typeName(
        ) == "long", "Casting of column"
        assert output_df.first()[name] == value, "Processing of column value"

    # fmt: off
    @pytest.mark.parametrize(("input_value", "value"), [
        (0,           0),              # minimum valid timestamp
        (-1,          None),           # minimum valid timestamp - 1 s
        (None,        None),
        (4102358400,  4102358400000),  # maximum valid timestamp
        (4102358401,  None),           # maximum valid timestamp + 1 s
        (5049688276,  None),
        (3469296996,  3469296996000),
        (7405162940,  None),
        (2769601503,  2769601503000),
        (-1429593275, None),
        (3412549669,  3412549669000),
    ])
    # fmt: on
    def test_generate_select_expression_for_timestamp_s_to_ms(
            self, input_value, value, spark_session, spark_context):
        source_key, name = "updated_at", "updated_at_ms"
        input_df = get_input_df(spark_session, spark_context, source_key,
                                input_value)
        result_column = custom_types._generate_select_expression_for_timestamp_s_to_ms(
            source_column=input_df["attributes"]["data"][source_key],
            name=name)
        output_df = input_df.select(result_column)

        assert output_df.schema.fieldNames() == [name], "Renaming of column"
        assert output_df.schema[name].dataType.typeName(
        ) == "long", "Casting of column"
        assert output_df.first()[name] == value, "Processing of column value"

    # fmt: off
    @pytest.mark.parametrize(("input_value", "value"), [
        (0,           0),           # minimum valid timestamp
        (-1,          None),        # minimum valid timestamp - 1 s
        (None,        None),
        (4102358400,  4102358400),  # maximum valid timestamp
        (4102358401,  None),        # maximum valid timestamp + 1 s
        (5049688276,  None),
        (3469296996,  3469296996),
        (7405162940,  None),
        (2769601503,  2769601503),
        (-1429593275, None),
        (3412549669,  3412549669),
    ])
    # fmt: on
    def test_generate_select_expression_for_timestamp_s_to_s(
            self, input_value, value, spark_session, spark_context):
        source_key, name = "updated_at", "updated_at_ms"
        input_df = get_input_df(spark_session, spark_context, source_key,
                                input_value)
        result_column = custom_types._generate_select_expression_for_timestamp_s_to_s(
            source_column=input_df["attributes"]["data"][source_key],
            name=name)
        output_df = input_df.select(result_column)

        assert output_df.schema.fieldNames() == [name], "Renaming of column"
        assert output_df.schema[name].dataType.typeName(
        ) == "long", "Casting of column"
        assert output_df.first()[name] == value, "Processing of column value"


class TestAddCustomDataTypeInRuntime(object):

    @staticmethod
    def _generate_select_expression_for_HelloWorld(source_column, name):
        from pyspark.sql import types as sql_types
        from pyspark.sql.functions import udf

        def _to_hello_world(col):
            if not col:
                return None
            else:
                return "Hello World"

        udf_hello_world = udf(_to_hello_world, sql_types.StringType())
        return udf_hello_world(source_column).alias(name)

    def test_custom_data_type_is_added(self, mocker):
        source_column, name = "element.key", "element_key"
        custom_types.add_custom_data_type(
            function_name="_generate_select_expression_for_HelloWorld",
            func=self._generate_select_expression_for_HelloWorld)

        mocked_function = mocker.patch.object(custom_types,
                                              "_generate_select_expression_for_HelloWorld")
        custom_types._get_select_expression_for_custom_type(source_column,
                                                           name,
                                                           "HelloWorld")

        mocked_function.assert_called_once_with(source_column, name)

    # fmt: off
    @pytest.mark.parametrize(("input_value", "value"), [
        ("Some other string", "Hello World"),
        ("",                  None),
        (None,                None),
        (" ",                 "Hello World"),
        (100,                 "Hello World"),
        (0,                   None)
    ])
    # fmt: on
    def test_custom_data_type_is_applied(self, input_value, value, spark_session, spark_context):
        custom_types.add_custom_data_type(
            function_name="_generate_select_expression_for_HelloWorld",
            func=self._generate_select_expression_for_HelloWorld)

        source_key, name, data_type = "key_name", "key", "HelloWorld"
        input_df = get_input_df(spark_session, spark_context, source_key, input_value)

        result_column = custom_types._get_select_expression_for_custom_type(
            source_column=input_df["attributes"]["data"][source_key],
            name=name,
            data_type=data_type
        )

        output_df = input_df.select(result_column)

        assert output_df.schema.fieldNames() == [name], "Renaming of column"
        assert output_df.schema[name].dataType.typeName(
        ) == "string", "Casting of column"
        assert output_df.first()[name] == value, "Processing of column value"

    def test_multiple_columns_are_accessed(self, spark_session):
        input_df = spark_session.createDataFrame([
            Row(first_name="David", last_name="Eigenstuhler"),
            Row(first_name="Katharina", last_name="Hohensinn"),
            Row(first_name="Nora", last_name="Hohensinn"),
        ])
        input_values = input_df.rdd.map(lambda x: x.asDict()).collect()
        expected_values = [d["first_name"] + "_" + d["last_name"] for d in input_values]

        def _first_and_last_name(source_column, name):
            return F.concat_ws("_", source_column, F.col("last_name")).alias(name)

        custom_types.add_custom_data_type(function_name="fullname", func=_first_and_last_name)

        output_df = Mapper([("full_name", "first_name", "fullname")]).transform(input_df)

        output_values = output_df.rdd.map(lambda x: x.asDict()["full_name"]).collect()

        assert expected_values == output_values

    def test_function_name_is_shortened(self, spark_session):
        input_df = spark_session.createDataFrame([
            Row(first_name="David"),
            Row(first_name="Katharina"),
            Row(first_name="Nora"),
        ])
        input_values = input_df.rdd.map(lambda x: x.asDict()["first_name"]).collect()
        expected_values = [fn.lower() for fn in input_values]

        def _lowercase(source_column, name):
            return F.lower(source_column).alias(name)

        custom_types.add_custom_data_type(function_name="lowercase", func=_lowercase)

        output_df = Mapper([("first_name", "first_name", "lowercase")]).transform(input_df)
        output_values = output_df.rdd.map(lambda x: x.asDict()["first_name"]).collect()

        assert expected_values == output_values
