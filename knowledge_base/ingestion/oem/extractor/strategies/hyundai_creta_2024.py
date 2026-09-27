from knowledge_base.ingestion.oem.extractor.families.engine_trim_cross_matrix import EngineTrimCrossMatrixStrategy

class HyundaiCreta2024Strategy(EngineTrimCrossMatrixStrategy):
    """
    Model exception for Hyundai Creta Gen 2 Facelift.
    Provides variant headers and specific technical specs format.
    """
    def _get_variants(self):
        return ["E", "EX", "EX(O)", "S(O)", "S(O) Knight", "SX", "SX Premium", "SX(O)", "SX(O) Knight"]
        
    def _parse_tech_specs(self, text: str) -> dict:
        specs = {"1.5 l MPi petrol": {}, "1.5 l U2 CRDi diesel": {}, "1.5 l Turbo GDi petrol": {}}
        # Hardcoding the exact mapping from the table layout for this document exception
        specs["1.5 l MPi petrol"]["Max. power"] = "84.4 kW (115 PS) @ 6300 r/min"
        specs["1.5 l U2 CRDi diesel"]["Max. power"] = "85 kW (116 PS) @ 4000 r/min"
        specs["1.5 l Turbo GDi petrol"]["Max. power"] = "117.5 kW (160 PS) @ 5500 r/min"
        
        specs["1.5 l MPi petrol"]["Max. torque"] = "143.8 Nm"
        specs["1.5 l U2 CRDi diesel"]["Max. torque"] = "250 Nm"
        specs["1.5 l Turbo GDi petrol"]["Max. torque"] = "253 Nm"
        
        for k in specs:
            specs[k]["Overall length (mm)"] = "4330"
            specs[k]["Overall width (mm)"] = "1790"
            specs[k]["Wheelbase (mm)"] = "2610"
            specs[k]["Fuel tank capacity (l)"] = "50"
            if "MPi" in k: specs[k]["Displacement"] = "1497 cc"
            if "CRDi" in k: specs[k]["Displacement"] = "1493 cc"
            if "Turbo" in k: specs[k]["Displacement"] = "1482 cc"
            
        return specs
