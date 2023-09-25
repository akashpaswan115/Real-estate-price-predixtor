from abc import ABC, abstractmethod
from pathlib import Path
from warnings import filterwarnings, warn

import dill
import numpy as np
import pandas as pd
from sklearn.metrics import mean_absolute_error
from sklearn.model_selection import cross_val_score, train_test_split
from sklearn.pipeline import Pipeline
from streamlit.elements.lib.mutable_status_container import StatusContainer

from src.core import io
from src.core.errors import ModelNotFoundError
from src.database.schema_reader import SchemaReader
from src.ml import model_details
from src.property import _utils
from src.typing import DatasetType, ModelType, PropertyAlias

filterwarnings("ignore", category=UserWarning)


class PropertyType(ABC):
    """Abstract class for to for different property type in real estate."""

    schema: SchemaReader
    prop_type: PropertyAlias
    _PROPERTY_TYPE: str

    @property
    def _ord_cols(self) -> dict[str, list[str | int]] | None:
        return {
            k: v
            for k in self.schema.CAT_COLS["ord_cols"]
            for i, v in _utils.ORD_COLS_MAPPING.items()
            if i == k
        }

    @abstractmethod
    def st_form(cls) -> None:
        ...

    @abstractmethod
    def extract_this_property(self, df: pd.DataFrame) -> pd.DataFrame:
        ...

    def dump_dataframe(
        self,
        df: pd.DataFrame,
        dataset_type: DatasetType,
        extend: bool,
    ) -> None:
        """For now store the data at `data/processed/props` directory."""
        fp = Path("data") / dataset_type / f"{self.prop_type}.csv"

        if fp.exists() and extend:
            old_df = pd.read_csv(fp)
            df = pd.concat([old_df, df], axis="index").drop_duplicates(["PROP_ID"])

        df.to_csv(fp, index=False)

    def get_model_path(self, dataset_type: DatasetType, model_type: ModelType) -> Path:
        return Path("models/") / dataset_type / model_type / f"{self.prop_type}.dill"

    def get_dataset_path(self, dataset_type: DatasetType) -> Path:
        return Path("data") / dataset_type / f"{self.prop_type}.csv"

    def store_model_details(
        self,
        dataset_type: DatasetType,
        model_type: ModelType,
        *,
        st_status: StatusContainer,
    ) -> None:
        model_path = self.get_model_path(dataset_type, model_type)
        df = io.read_csv(self.get_dataset_path(dataset_type))

        X = df.drop(columns=["PRICE"])
        y = np.log1p(df["PRICE"])

        X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.25, random_state=42)

        # Load model
        try:
            with open(model_path, "rb") as f:
                pipeline: Pipeline = dill.load(f)
        except FileNotFoundError:
            raise ModelNotFoundError(f"Model for {self.prop_type} is not trained yet.")

        st_status.write("Calculating Cross Validation Score (R2 Score)...")
        scores = cross_val_score(estimator=pipeline, X=X_train, y=y_train, cv=5, scoring="r2")

        try:
            st_status.write("Predicting `X_test` for more scoring metrics...")
            y_pred = np.expm1(pipeline.predict(X_test))
        except ValueError as e:  # When any/some predicted value become inf or NaN
            st_status.error(str(e), icon="🛑")
            st_status.update(
                label="Error while predicting `X_test`.",
                expanded=False,
                state="error",
            )
            warn(str(e), category=UserWarning)
            y_pred = y_test

        st_status.write("Creating model scores details...")
        details = model_details.ModelDetailsItem(
            class_name=pipeline.named_steps["reg_model"].__class__.__name__,
            r2_score_mean=round(scores.mean(), 3),
            r2_score_std=round(scores.std(), 3),
            mae=round(float(mean_absolute_error(np.expm1(y_test), y_pred)), 3),
        )

        st_status.write("Storing the model scores details...")
        model_details_path = model_details.get_model_details_file_path(dataset_type, model_type)
        model_details.append_details(model_details_path, self.prop_type, details)
