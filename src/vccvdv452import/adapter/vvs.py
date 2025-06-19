import logging

from typing import Tuple

from vcclib import database
from vcclib.model import Line
from vccvdv452import.adapter.default import DefaultAdapter


class VvsAdapter(DefaultAdapter):

    def _extract_line_data(self, input_directory: str, batch_size: int) -> Tuple[dict, dict]:
        line_index: dict = dict()
        line_direction_index: dict = dict()

        transaction = database.connection().transaction()
        transation_count = 0

        x10_rec_lid = self._internal_read_x10_file(input_directory, 'rec_lid.x10')
        for i, record in enumerate(x10_rec_lid.records):
            try:
                line_id = record['LI_NR']
                line_variant_id = record['STR_LI_VAR']
                direction = record['LI_RI_NR']
                name = record['LI_KUERZEL']
                
                if 'LinienID' in record:
                    international_id = record['LinienID']
                else:
                    international_id = None

                if (line_id, line_variant_id) not in line_direction_index:
                    line_direction_index[(line_id, line_variant_id)] = direction

                if line_id not in line_index:
                    line_index[line_id] = Line(
                        line_id=line_id, 
                        name=name,
                        international_id=international_id, 
                        connection=transaction
                    )

                    transation_count = transation_count + 1

                if transation_count >= batch_size or i >= len(x10_rec_lid.records) - 1:
                    transaction.commit()

                    transaction = database.connection().transaction()
                    transation_count = 0

            except Exception as ex:
                transaction.rollback()
                transaction_count = 0

                if not i >= len(x10_rec_lid.records) - 1:
                    transaction = database.connection().transaction()

                logging.exception(ex)
    
        x10_rec_lid.close()

        return line_index, line_direction_index

    """def _convert_coordinate(self, input: float|str) -> float:
        if type(input) == str:
            input = float(input)
            
        return input / 10000000.0"""