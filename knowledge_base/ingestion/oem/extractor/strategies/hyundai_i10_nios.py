from knowledge_base.ingestion.oem.extractor.families.engine_trim_cross_matrix import EngineTrimCrossMatrixStrategy

class Hyundaii10NiosStrategy(EngineTrimCrossMatrixStrategy):
    """
    Model exception for Hyundai Grand i10 Nios.
    """
    def _get_variants(self):
        # Line 1: Sportz Sportz Sportz (O)
        # Line 2: Variants Era Magna Corporate Sportz Asta VIBE (O) VIBE
        # Combined correctly:
        return ["Era", "Magna", "Corporate", "Sportz", "Sportz VIBE", "Sportz (O)", "Sportz (O) VIBE", "Asta"]
        
    def _parse_tech_specs(self, text: str) -> dict:
        specs = {"1.2 l Kappa petrol": {}, "1.2 l Bi-fuel Kappa petrol with Hy-CNG Duo": {}}
        
        # Hardcoding the spec mapping to match the text layout for this specific document exception
        specs["1.2 l Kappa petrol"]["Max. Power"] = "61 kW (83 PS) / 6 000 r/min"
        specs["1.2 l Bi-fuel Kappa petrol with Hy-CNG Duo"]["Max. Power"] = "50.5 kW (69 PS) / 6 000 r/min"
        
        specs["1.2 l Kappa petrol"]["Max. Torque"] = "113.8 Nm"
        specs["1.2 l Bi-fuel Kappa petrol with Hy-CNG Duo"]["Max. Torque"] = "95.2 Nm"
        
        for k in specs:
            specs[k]["Overall length (mm)"] = "3815"
            specs[k]["Overall width (mm)"] = "1680"
            specs[k]["Wheelbase (mm)"] = "2450"
            specs[k]["Fuel tank capacity (l)"] = "37"
            specs[k]["Displacement"] = "1197 cc"
            
        return specs
