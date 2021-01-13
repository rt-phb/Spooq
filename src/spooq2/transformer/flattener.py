from pyspark.sql import functions as f, types as T
import sys
import json

from .transformer import Transformer
from spooq2.transformer import Exploder, Mapper


class Flattener(Transformer):
    """
    Flattens input DataFrame schema and applies it to the DataFrame.
    """

    def transform(self, input_df):
        preliminary_mapping = self._get_preliminary_mapping(input_df.schema.jsonValue(), [], [])
        # exploded_df, mapping = self._magic(input_df, input_df.schema.jsonValue(),
        #                                    mapping=[], current_path=[])
        fixed_mapping = self._convert_python_to_spark_data_types(preliminary_mapping)
        mapped_df = Mapper(mapping=fixed_mapping).transform(input_df)
        # import IPython; IPython.embed()
        return mapped_df

    def _get_preliminary_mapping(self, json_schema, mapping, current_path):
        for field in json_schema["fields"]:
            if self._is_atomic_data_type(field):
                print("Atomic Field:")
                print(json.dumps(field, indent=2))
                # base case (no more children)
                mapping = self._add_mapping(mapping, current_path, field)
            elif self._is_struct(field):
                print("Struct Field:")
                print(json.dumps(field, indent=2))
                struct_name = field.get("name")
                new_path = current_path + [struct_name]
                print(f"struct_name: {struct_name}")
                print(f"current_path: {current_path}")
                print(f"new_path: {new_path}")
                mapping = self._get_preliminary_mapping(field["type"], mapping, new_path)
            # elif self._is_array(field):
            #     current_path = self._add_star_to_path()
            #     self._get_preliminary_mapping(field, mapping, current_path)
        return mapping

    def _is_atomic_data_type(self, field):
        return isinstance(field["type"], str)

    def _add_mapping(self, mapping, current_path, field):
        field_name = "_".join(current_path + [field["name"]])
        full_path = ".".join(current_path + [field["name"]])
        data_type = field["type"]
        mapping.append((field_name, full_path, data_type))
        return mapping

    def _is_struct(self, field):
        field_type = field["type"]
        return (isinstance(field_type, dict) and
                len(field_type.get("fields", [])) > 0 and
                field_type.get("type", "") == "struct")

    # def _is_array(self, field):
    #     field_type = field["type"]
    #     return (isinstance(field_type, dict) and
    #             "fields" not in field_type.keys() and
    #             field_type.get("type", "") == "array")
    #
    # def _explode_array(self, input_df, ):

    # def _get_children(self, json_schema):
    #     num_fields = len(json_schema.get("fields", -1))
    #     for field in json_schema["fields"]:
    #         field_name = field["name"]
    #         field_type = field["type"]
    #         full_path = ".".join(current_path + [field_name])
    #
    # def _magic(self, input_df, json_schema, mapping, current_path, exploded_arrays=[]):
    #     print("input_df printed schema: ")
    #     input_df.printSchema()
    #     print(f"json_schema: {json.dumps(json_schema, indent=2)}")
    #     for field in json_schema["fields"]:
    #         field_name = field["name"]
    #         field_type = field["type"]
    #         full_path = ".".join(current_path + [field_name])
    #         print(f"field_name: {field_name}, field_type: {field_type}, full_path: {full_path}")
    #         print(f"mapping: {json.dumps(mapping, indent=2)}")
    #         print(f"current_path: {current_path}")
    #         if isinstance(field_type, dict):
    #             #  Complex Data Type
    #             if field_type["type"] == "struct":
    #                 print("is struct!")
    #                 return self._magic(input_df, field_type, mapping, current_path + [field_name], exploded_arrays)
    #                 break
    #             elif field_type["type"] == "array":
    #                 print("is array!")
    #                 print("Incoming Schema:")
    #                 input_df.printSchema()
    #                 print(f"current_path: {current_path}")
    #                 print(f"exploded_arrays: {exploded_arrays}")
    #                 exploded_full_path = f"{full_path.replace('.', '_')}_exploded"
    #                 print(f"Exploder param |path_to_array| -> {full_path}")
    #                 print(f"Exploder param |exploded_elem_name| -> {exploded_full_path}")
    #                 exploded_df = Exploder(
    #                     path_to_array=full_path,
    #                     exploded_elem_name=exploded_full_path
    #                 ).transform(input_df)
    #                 print("Exploded Schema:")
    #                 exploded_df.printSchema()
    #                 return self._magic(exploded_df, exploded_df.schema.jsonValue(), [], current_path, exploded_full_path)
    #                 break
    #         elif isinstance(field_type, str):
    #             #  Primitive Data Type
    #             full_field_name = full_path.replace('.', '_')
    #             if full_field_name not in [name for (name, source, type) in mapping]:
    #                 mapping.append((full_field_name, full_path, field["type"]))
    #         else:
    #             raise("field_type should either be a string or a dict! I'm confused...")
    #     return (input_df, mapping)
    #
    def _convert_python_to_spark_data_types(self, mapping):
        data_type_matrix = {
            "long": "LongType",
            "int": "IntegerType",
            "string": "StringType",
            "double": "DoubleType",
            "float": "FloatType",
            "boolean": "BooleanType",
            "date": "DateType",
            "timestamp": "TimestampType"
        }
        try:
            return [(name, source, data_type_matrix[data_type]) for (name, source, data_type) in mapping]
        except Exception as e:
            import IPython; IPython.embed()

    #
    # def _explode_array(self, input_df):
    #     import IPython; IPython.embed()
    #     schema = input_df.schema
    #     for field in schema.fields:
    #         json_value = field.jsonValue()
    #         field_name = json_value["name"]
    #         data_type = json_value["type"]
    #         if isinstance(data_type, dict) and data_type.get("type", None) == "array":
    #             element_type = json_value["type"]["elementType"]
    #         if field_name.endswith("_exploded_exploded"):
    #             # fix ugly names for nested arrays
    #             input_df = input_df.withColumnRenamed(field_name, field_name.replace("_exploded_exploded", "_exploded"))
    #     return input_df
    #
    # def _get_mapping_for_struct(self, input_df, current_path=[]):
    #     json_schema = input_df.schema.jsonValue()
    #     raise("Not a Struct!") if json_schema.type != "struct" else None
    #
    #
