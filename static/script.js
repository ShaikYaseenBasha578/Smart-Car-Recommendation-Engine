// 🆕 New Car Handler
async function sendQuery(event) {
    if (event) {
        event.preventDefault();
    }

    const userInput = document.getElementById("userQuery").value;
    const resultBox = document.getElementById("results");

    resultBox.innerHTML = "<p>Loading recommendations...</p>";

    try {
        const response = await fetch("/predict", {
            method: "POST",
            headers: { 
                "Content-Type": "application/json" 
            },
            body: JSON.stringify({ query: userInput })
        });

        const data = await response.json();

        console.log("Full backend response:", data);
        console.log("Recommendations:", data.recommendations);

        resultBox.innerHTML = "";

        if (!response.ok) {
            resultBox.innerHTML = `<p>Error: ${data.error || "Something went wrong."}</p>`;
            return;
        }

        if (data.message) {
            resultBox.innerHTML = `<p>${data.message}</p>`;
            return;
        }

        if (!data.recommendations || data.recommendations.length === 0) {
            resultBox.innerHTML = "<p>No recommendations found.</p>";
            return;
        }

        data.recommendations.forEach(car => {
            const item = document.createElement("div");
            item.classList.add("elements");

            const price = car["Ex-Showroom_Price"]
                ? Math.round(car["Ex-Showroom_Price"]).toLocaleString("en-IN")
                : "N/A";

            const mileage = car["ARAI_Certified_Mileage"]
                ? Number(car["ARAI_Certified_Mileage"]).toFixed(1)
                : "N/A";

            const reasons = car.match_reasons && car.match_reasons.length > 0
                ? `<p><strong>Why:</strong> ${car.match_reasons.join(", ")}</p>`
                : "";

            item.innerHTML = `
                <img src="${car.carImage || "/static/car_images/pic1.avif"}" 
                     alt="${car.Make || "Car"} ${car.Model || ""}">

                <div class="t">
                    <h1>${car.Make || "Unknown"} ${car.Model || ""} ${car.Variant || ""}</h1>

                    <div class="p">
                        <p>₹${price}</p>
                        <p>Mileage: ${mileage} kmpl</p>
                        <p>Transmission: ${car.Transmission || "Not specified"}</p>
                        <p>Fuel: ${car.Fuel_Type || "Not specified"}</p>
                        ${reasons}
                    </div>

                    <div class="links">
                        <a href="${car.carDekhoLink || "#"}" target="_blank">CarDekho</a>
                        <a href="${car.carWaleLink || "#"}" target="_blank">CarWale</a>
                    </div>
                </div>
            `;

            resultBox.appendChild(item);
        });

    } catch (error) {
        console.error("Frontend error:", error);
        resultBox.innerHTML = `<p>Frontend error. Check browser console.</p>`;
    }
}