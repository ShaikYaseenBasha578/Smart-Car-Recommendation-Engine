#!/bin/bash

download_and_hash() {
    local url=$1
    local out_path=$2
    echo "Downloading $url to $out_path"
    curl -sL -A "Mozilla/5.0" "$url" -o "$out_path"
    shasum -a 256 "$out_path"
}

download_and_hash "https://www.marutisuzuki.com/content/dam/msil/arena/in/en/assets/cars/wagonr/documents/Arena-Wagon-r-Brochure.pdf" "knowledge_base/sources/oem/maruti_suzuki/wagon_r/latest/brochures/WagonR_Brochure.pdf"
download_and_hash "https://www.hyundai.com/content/dam/hyundai/in/en/data/brochure/grand-i10-nios.pdf" "knowledge_base/sources/oem/hyundai/grand_i10_nios/latest/brochures/Grand_i10_Nios_Brochure.pdf"
download_and_hash "https://www.nexaexperience.com/content/dam/msil/nexa/in/en/assets/cars/fronx/documents/NEXA-Fronx-Brochure.pdf" "knowledge_base/sources/oem/maruti_suzuki/fronx/latest/brochures/Fronx_Brochure.pdf"
download_and_hash "https://www.nexaexperience.com/content/dam/msil/nexa/in/en/assets/cars/newbaleno/download-brochure/The-Stunning-New-Baleno-Brochure.pdf" "knowledge_base/sources/oem/maruti_suzuki/baleno/latest/brochures/Baleno_Brochure.pdf"
