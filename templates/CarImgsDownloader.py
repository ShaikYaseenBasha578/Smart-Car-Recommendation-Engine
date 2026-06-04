import os
import time
import requests
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options

car_list = [
    {'Make': 'Maruti Suzuki', 'Model': 'Eeco'},
    {'Make': 'Tata', 'Model': 'Nano Genx'},
    {'Make': 'Datsun', 'Model': 'Redi-Go'},
    {'Make': 'Renault', 'Model': ' Kwid'},
    {'Make': 'Maruti Suzuki', 'Model': 'Alto K10'},
    {'Make': 'Datsun', 'Model': 'Go'},
    {'Make': 'Maruti Suzuki', 'Model': 'Celerio Tour'},
    {'Make': 'Hyundai', 'Model': 'Santro'},
    {'Make': 'Tata', 'Model': 'Tiago'},
    {'Make': 'Maruti Suzuki', 'Model': 'Celerio X'},
    {'Make': 'Maruti Suzuki', 'Model': 'Ignis'},
    {'Make': 'Renault', 'Model': 'Triber'},
    {'Make': 'Toyota', 'Model': 'Etios Liva'},
    {'Make': 'Nissan', 'Model': 'Micra Active'},
    {'Make': 'Hyundai', 'Model': 'Xcent Prime'},
    {'Make': 'Maruti Suzuki', 'Model': 'Dzire Tour'},
    {'Make': 'Hyundai', 'Model': 'Elite I20'},
    {'Make': 'Hyundai', 'Model': 'Aura'},
    {'Make': 'Volkswagen', 'Model': 'Polo'},
    {'Make': 'Maruti Suzuki', 'Model': 'Dzire'},
    {'Make': 'Ford', 'Model': 'Freestyle'},
    {'Make': 'Volkswagen', 'Model': 'Ameo'},
    {'Make': 'Ford', 'Model': 'Aspire'},
    {'Make': 'Toyota', 'Model': 'Etios Cross'},
    {'Make': 'Toyota', 'Model': 'Glanza'},
    {'Make': 'Honda', 'Model': 'Jazz'},
    {'Make': 'Maruti Suzuki', 'Model': 'Vitara Brezza'},
    {'Make': 'Hyundai', 'Model': 'I20 Active'},
    {'Make': 'Renault', 'Model': 'Duster'},
    {'Make': 'Hyundai', 'Model': 'Verna'},
    {'Make': 'Mahindra', 'Model': 'Xuv300'},
    {'Make': 'Renault', 'Model': 'Lodgy'},
    {'Make': 'Volkswagen', 'Model': 'Vento'},
    {'Make': 'Honda', 'Model': 'Brv'},
    {'Make': 'Tata', 'Model': 'Tigor Ev'},
    {'Make': 'Mahindra', 'Model': 'Thar'},
    {'Make': 'Force', 'Model': 'Gurkha'},
    {'Make': 'Maruti Suzuki', 'Model': 'Xl6'},
    {'Make': 'Tata', 'Model': 'Hexa'},
    {'Make': 'Toyota', 'Model': 'Innova Crysta'},
    {'Make': 'Jeep', 'Model': 'Compass'},
    {'Make': 'Toyota', 'Model': 'Corolla Altis'},
    {'Make': 'Honda', 'Model': 'Civic'},
    {'Make': 'Mg', 'Model': 'Zs Ev'},
    {'Make': 'Kia', 'Model': 'Carnival'},
    {'Make': 'Skoda', 'Model': 'Superb'},
    {'Make': 'Toyota', 'Model': 'Fortuner'},
    {'Make': 'Mitsubishi', 'Model': 'Pajero Sport'},
    {'Make': 'Volvo', 'Model': 'V40'},
    {'Make': 'Ford', 'Model': 'Endeavour'},
    {'Make': 'Volvo', 'Model': 'V40 Cross Country'},
    {'Make': 'Mini', 'Model': 'Cooper 3 Door'},
    {'Make': 'Skoda', 'Model': 'Kodiaq Scout'},
    {'Make': 'Mini', 'Model': 'Countryman'},
    {'Make': 'Bmw', 'Model': 'X1'},
    {'Make': 'Toyota', 'Model': 'Camry'},
    {'Make': 'Volvo', 'Model': 'S60'},
    {'Make': 'Bmw', 'Model': '3-Series'},
    {'Make': 'Honda', 'Model': 'Accord Hybrid'},
    {'Make': 'Toyota', 'Model': 'Prius'},
    {'Make': 'Land Rover Rover', 'Model': 'Range Evoque'},
    {'Make': 'Bmw', 'Model': '5-Series'},
    {'Make': 'Lexus', 'Model': 'Nx 300H'},
    {'Make': 'Audi', 'Model': 'A5'},
    {'Make': 'Lexus', 'Model': 'Es'},
    {'Make': 'Jaguar', 'Model': 'F-Pace'},
    {'Make': 'Bmw', 'Model': '6-Series'},
    {'Make': 'Volvo', 'Model': 'V90 Cross Country'},
    {'Make': 'Porsche', 'Model': 'Macan'},
    {'Make': 'Mitsubishi', 'Model': 'Montero'},
    {'Make': 'Land Rover', 'Model': 'Discovery'},
    {'Make': 'Volvo', 'Model': 'Xc90'},
    {'Make': 'Jaguar', 'Model': 'F-Type'},
    {'Make': 'Jaguar', 'Model': 'Xj'},
    {'Make': 'Bmw', 'Model': 'X7'},
    {'Make': 'Porsche', 'Model': 'Cayenne'},
    {'Make': 'Maserati', 'Model': 'Ghibli'},
    {'Make': 'Bmw', 'Model': 'M5'},
    {'Make': 'Toyota', 'Model': 'X7'},
    {'Make': 'Audi', 'Model': 'Rs7'},
    {'Make': 'Porsche', 'Model': '911'},
    {'Make': 'Lexus', 'Model': 'Lc 500H'},
    {'Make': 'Porsche', 'Model': 'Panamera'},
    {'Make': 'Lexus', 'Model': 'Lx 450D'},
    {'Make': 'Audi', 'Model': 'R8'},
    {'Make': 'Lamborghini', 'Model': 'Urus'},
    {'Make': 'Bentley', 'Model': 'Continental Gt'},
    {'Make': 'Ferrari', 'Model': 'Portofino'},
    {'Make': 'Bentley', 'Model': 'Bentayga'},
    {'Make': 'Maruti Suzuki', 'Model': 'Alto'},
    {'Make': 'Maruti Suzuki', 'Model': 'S-Presso'},
    {'Make': 'Maruti Suzuki', 'Model': 'Celerio'},
    {'Make': 'Hyundai', 'Model': 'Grand I10 Prime'},
    {'Make': 'Mahindra', 'Model': 'Kuv100 Nxt'},
    {'Make': 'Maruti Suzuki', 'Model': 'Swift'},
    {'Make': 'Tata', 'Model': 'Altroz'},
    {'Make': 'Tata', 'Model': 'Tigor'},
    {'Make': 'Tata', 'Model': 'Zest'},
    {'Make': 'Honda', 'Model': 'Amaze'},
    {'Make': 'Maruti Suzuki', 'Model': 'Gypsy'},
    {'Make': 'Hyundai', 'Model': 'Venue'},
    {'Make': 'Tata', 'Model': 'Nexon'},
    {'Make': 'Maruti Suzuki', 'Model': 'Ertiga'},
    {'Make': 'Maruti Suzuki', 'Model': 'Baleno Rs'},
    {'Make': 'Honda', 'Model': 'Wr-V'},
    {'Make': 'Mahindra', 'Model': 'Tuv300'},
    {'Make': 'Maruti Suzuki', 'Model': 'S-Cross'},
    {'Make': 'Kia', 'Model': 'Seltos'},
    {'Make': 'Mahindra', 'Model': 'Xylo'},
    {'Make': 'Renault', 'Model': 'Captur'},
    {'Make': 'Nissan', 'Model': 'Terrano'},
    {'Make': 'Tata', 'Model': 'Safari Storme'},
    {'Make': 'Mg', 'Model': 'Hector'},
    {'Make': 'Hyundai', 'Model': 'Elantra'},
    {'Make': 'Hyundai', 'Model': 'Tucson'},
    {'Make': 'Tata', 'Model': 'Nexon Ev'},
    {'Make': 'Volkswagen', 'Model': 'Passat'},
    {'Make': 'Isuzu', 'Model': 'Mu-X'},
    {'Make': 'Volkswagen', 'Model': 'Tiguan'},
    {'Make': 'Skoda', 'Model': 'Kodiaq'},
    {'Make': 'Audi', 'Model': 'Q3'},
    {'Make': 'Jaguar', 'Model': 'Xf'},
    {'Make': 'Audi', 'Model': 'A6'},
    {'Make': 'Land Rover', 'Model': 'Discovery Sport'},
    {'Make': 'Volvo', 'Model': 'Xc60'},
    {'Make': 'Jeep', 'Model': 'Wrangler'},
    {'Make': 'Audi', 'Model': 'Q7'},
    {'Make': 'Lamborghini', 'Model': 'Huracan'},
    {'Make': 'Maruti Suzuki', 'Model': 'Baleno'},
    {'Make': 'Hyundai', 'Model': 'Grand I10'},
    {'Make': 'Nissan', 'Model': 'Sunny'},
    {'Make': 'Mahindra', 'Model': 'Bolero'},
    {'Make': 'Maruti Suzuki', 'Model': 'Ciaz'},
    {'Make': 'Skoda', 'Model': 'Rapid'},
    {'Make': 'Hyundai', 'Model': 'Creta'},
    {'Make': 'Tata', 'Model': 'Harrier'},
    {'Make': 'Jeep', 'Model': 'Compass Trailhawk'},
    {'Make': 'Honda', 'Model': 'Cr-V'},
    {'Make': 'Hyundai', 'Model': 'Grand I10 Nios'},
    {'Make': 'Hyundai', 'Model': 'Xcent'},
    {'Make': 'Nissan', 'Model': 'Kicks'},
    {'Make': 'Nissan', 'Model': 'Micra'},
    {'Make': 'Audi', 'Model': 'A3'},
    {'Make': 'Volvo', 'Model': 'Xc40'},
    {'Make': 'Toyota', 'Model': 'Yaris'},
    {'Make': 'Tata', 'Model': 'Tiago Nrg'},
    {'Make': 'Skoda', 'Model': 'Octavia'},
    {'Make': 'Honda', 'Model': 'City'},
    {'Make': 'Bmw', 'Model': 'X4'},
    {'Make': 'Bmw', 'Model': 'X5'},
    {'Make': 'Mahindra', 'Model': 'Alturas G4'},
    {'Make': 'Jaguar', 'Model': 'Xe'},
    {'Make': 'Mahindra', 'Model': 'Verito'},
    {'Make': 'Bmw', 'Model': 'X3'},

]

chrome_options = Options()
# chrome_options.add_argument("--headless")  # Keep visible for debug
chrome_options.add_argument("user-agent=Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/116.0.5845.96 Safari/537.36")

driver_path = "/Users/shaikyaseenbasha/.wdm/drivers/chromedriver/mac64/137.0.7151.119/chromedriver-mac-arm64/chromedriver"
service = Service(driver_path)
driver = webdriver.Chrome(service=service, options=chrome_options)

output_dir = 'static/car_images'
os.makedirs(output_dir, exist_ok=True)

for car in car_list:
    make = car['Make'].lower()
    model = car['Model'].lower().replace(" ", "-")
    file_name = f"{make}_{model}.jpg"
    save_path = os.path.join(output_dir, file_name)

    url = f"https://www.cardekho.com/{make}/{model}"
    print(f"Processing: {url}")

    try:
        driver.get(url)
        time.sleep(5)  # Let JS load fully

        # Print HTML to check what Selenium sees:
        print(driver.page_source[:1000])

        img_element = driver.find_element(By.CSS_SELECTOR, 'img[alt*="Front Left"]')
        img_url = img_element.get_attribute("src")
        print(f"Image URL found: {img_url}")

        if img_url and img_url.startswith('http'):
            img_data = requests.get(img_url).content
            with open(save_path, 'wb') as handler:
                handler.write(img_data)
            print(f"Image saved: {save_path}")
        else:
            print(f"No valid image URL for {make} {model}")

    except Exception as e:
        print(f"Error for {make} {model}: {e}")

driver.quit()
print("✅ All done.")
