import pandas as pd
import streamlit as st

from src.database.schema_reader import SchemaReader
from src.property import _utils
from src.property.form_field import FormField

from ..property_type import PropertyType


class RentIndFloor(PropertyType):
    schema = SchemaReader("rent_ind_floor")
    prop_type = "rent_ind_floor"
    _PROPERTY_TYPE = "independent/builder floor"

    @staticmethod
    def st_form():
        FormField.AREA()
        FormField.FACING()

        l, r = st.columns(2)
        FormField.AGE(pos=l)
        FormField.FURNISH(pos=r)

        l, m, r = st.columns(3)
        FormField.BEDROOM_NUM(pos=l)
        FormField.BALCONY_NUM(pos=m)
        FormField.FLOOR_NUM(pos=r)

        FormField.LUXURY_CATEGORY()

    def extract_this_property(self, df: pd.DataFrame) -> pd.DataFrame:
        df = df.query("PROPERTY_TYPE==@self._PROPERTY_TYPE").reset_index(drop=True)
        df = _utils.query_for_rental_property(df, "PRICE<8_00_000")

        df["PROP_ID"] = self.prop_type
        return df
