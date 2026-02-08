// Dynamically set API based on environment
const API = window.location.hostname === 'localhost' 
  ? "http://localhost:1000" 
  : window.location.origin;

// Check if user is logged in
document.addEventListener('DOMContentLoaded', () => {
  const token = localStorage.getItem('token');
  if (!token) {
    window.location.href = '/';
    return;
  }
  
  loadMedicines();
});

document.getElementById("medicineForm").onsubmit = async (e) => {
  e.preventDefault();

  const token = localStorage.getItem('token');
  const data = {
    name: document.getElementById("name").value,
    batch: document.getElementById("batch").value,
    expiry: document.getElementById("expiry").value,
    barcode: document.getElementById("barcode").value,
    quantity: parseInt(document.getElementById("quantity").value)
  };

  try {
    const res = await fetch(API + "/add", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "Authorization": `Bearer ${token}`
      },
      body: JSON.stringify(data)
    });

    if (res.status === 401) {
      localStorage.removeItem('token');
      window.location.href = '/';
      return;
    }

    if (!res.ok) {
      const error = await res.json();
      alert("Error: " + error.error);
      return;
    }

    document.getElementById("medicineForm").reset();
    loadMedicines();
  } catch (e) {
    alert("Failed to connect to server. Make sure backend is running!");
    console.error(e);
  }
};

async function loadMedicines() {
  const token = localStorage.getItem('token');
  try {
    const res = await fetch(API + "/medicines", {
      headers: {
        "Authorization": `Bearer ${token}`
      }
    });
    
    if (res.status === 401) {
      localStorage.removeItem('token');
      window.location.href = '/';
      return;
    }

    if (!res.ok) {
      throw new Error("Failed to fetch medicines: " + res.status);
    }
    
    const meds = await res.json();
    medicineList.innerHTML = "";

    if (!Array.isArray(meds)) {
      medicineList.innerHTML = "<p>Error loading medicines</p>";
      return;
    }

    if (meds.length === 0) {
      medicineList.innerHTML = "<p>No medicines added yet</p>";
      return;
    }

    meds.forEach(m => {
      medicineList.innerHTML += `
        <div class="card ${m.status}">
          <h3>${m.name}</h3>
          <p>Batch: ${m.batch}</p>
          <p>Expiry: ${m.expiry}</p>
          <p>Barcode: ${m.barcode}</p>
          <p>Quantity: ${m.quantity}</p>
          <p>Days Left: ${m.days_left}</p>
          <button onclick="deleteMed(${m.id})">Delete</button>
        </div>`;
    });
  } catch (e) {
    medicineList.innerHTML = "<p style='color:red'>⚠️ Cannot connect to server.</p>";
    console.error(e);
  }
}

async function deleteMed(id) {
  const token = localStorage.getItem('token');
  try {
    const res = await fetch(API + "/delete/" + id, {
      method: "DELETE",
      headers: {
        "Authorization": `Bearer ${token}`
      }
    });
    
    if (res.status === 401) {
      localStorage.removeItem('token');
      window.location.href = '/';
      return;
    }

    if (!res.ok) {
      const error = await res.json();
      alert("Error: " + error.error);
      return;
    }
    
    loadMedicines();
  } catch (e) {
    alert("Failed to delete medicine");
    console.error(e);
  }
}

function logout() {
  localStorage.removeItem('token');
  window.location.href = '/';
}
