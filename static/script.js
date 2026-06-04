// 🆕 New Car Handler
async function sendQuery() {
    const userInput = document.getElementById("userQuery").value;

    const response = await fetch("/predict", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ query: userInput })
    });

    const data = await response.json();
    const resultBox = document.getElementById("results");
    resultBox.innerHTML = "";

    if (data.recommendations) {
        data.recommendations.forEach(car => {
            const item = document.createElement("div");
            item.classList.add("elements");

            item.innerHTML = `
                <img src="${car.carImage}" alt="${car.Make} ${car.Model}">
                <div class="t">
                    <h1>${car.Make} ${car.Model} ${car.Variant}</h1>
                    <div class="p">
                        <p>₹${Math.round(car["Ex-Showroom_Price"]).toLocaleString()}</p>
                        <p>Mileage: ${car.ARAI_Certified_Mileage} kmpl</p>
                        <p>Transmission: ${car.Transmission}</p>
                        <p>Fuel: ${car.Fuel_Type}</p>
                    </div>
                    <div class="links">
                        <a href="${car.carDekhoLink}" target="_blank">CarDekho</a>
                        <a href="${car.carWaleLink}" target="_blank">CarWale</a>
                    </div>
                </div>
            `;

            resultBox.appendChild(item);
        });
    } else {
        resultBox.innerText = data.message || "No results.";
    }

    console.log(data.recommendations);
}


// 🆕 Used Car Handler
async function sendUsedQuery() {
    const userInput = document.getElementById("usedQuery").value;
    const resultBox = document.getElementById("used-results");
    const loader = document.getElementById("loading");
  
    resultBox.innerHTML = "";
    loader.style.display = "block";
  
    const response = await fetch("/used-cars", {
      method: "POST",
      headers: {
        "Content-Type": "application/json"
      },
      body: JSON.stringify({ query: userInput })
    });
  
    const data = await response.json();
    loader.style.display = "none";
  
    if (data.recommendations && data.recommendations.length > 0) {
      data.recommendations.forEach(car => {
        const item = document.createElement("div");
        item.classList.add("elements");
  
        item.innerHTML = `
          <img src="${car.image_url}" alt="${car.title}" loading="lazy">
          <div class="t">
            <h1>${car.title}</h1>
            <div class="p">
              <p>${car.price || 'Price not listed'}</p>
              <p>${car.km || 'KM unknown'} | ${car.fuel || ''} | ${car.transmission || ''}</p>
              <p>${car.owner ? 'Owner: ' + car.owner : ''}</p>
              <p>${car.location}</p>
            </div>
            <div class="links">
              <a href="${car.listing_url}" target="_blank">View Listing</a>
            </div>
          </div>
        `;
        resultBox.appendChild(item);
      });
    } else {
      resultBox.innerHTML = `<p>No used cars found for your query.</p>`;
    }
  }

  