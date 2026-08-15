const fmt = (n) => "₹" + Number(n || 0).toLocaleString("en-IN", { maximumFractionDigits: 2 });

let categoryChart, trendChart;

document.addEventListener("DOMContentLoaded", () => {
  document.querySelector('input[name="date"]').valueAsDate = new Date();
  loadTransactions();
  loadSummary();

  document.getElementById("txnForm").addEventListener("submit", async (e) => {
    e.preventDefault();
    const form = e.target;
    const payload = {
      type: form.type.value,
      amount: form.amount.value,
      category: form.category.value,
      date: form.date.value,
      note: form.note.value,
      is_recurring: form.is_recurring.checked,
    };
    const res = await fetch("/api/transactions", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    if (res.ok) {
      form.reset();
      document.querySelector('input[name="date"]').valueAsDate = new Date();
      loadTransactions();
      loadSummary();
    } else {
      const err = await res.json();
      alert(err.error || "Failed to add transaction");
    }
  });

  document.getElementById("budgetForm").addEventListener("submit", async (e) => {
    e.preventDefault();
    const budget = document.getElementById("budgetInput").value;
    await fetch("/api/budget", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ budget }),
    });
    loadSummary();
  });
});

async function loadTransactions() {
  const res = await fetch("/api/transactions");
  const txns = await res.json();
  const tbody = document.querySelector("#txnTable tbody");
  tbody.innerHTML = "";
  txns.forEach((t) => {
    const tr = document.createElement("tr");
    tr.innerHTML = `
      <td>${t.date}</td>
      <td><span class="badge ${t.type}">${t.type}</span></td>
      <td>${t.category}</td>
      <td>${t.note || ""}</td>
      <td class="${t.type}">${t.type === "expense" ? "-" : "+"}${fmt(t.amount)}</td>
      <td><button class="btn-delete" data-id="${t.id}">✕</button></td>
    `;
    tbody.appendChild(tr);
  });

  document.querySelectorAll(".btn-delete").forEach((btn) => {
    btn.addEventListener("click", async () => {
      await fetch(`/api/transactions/${btn.dataset.id}`, { method: "DELETE" });
      loadTransactions();
      loadSummary();
    });
  });
}

async function loadSummary() {
  const res = await fetch("/api/analytics/summary");
  const data = await res.json();

  document.getElementById("totalIncome").textContent = fmt(data.total_income);
  document.getElementById("totalExpense").textContent = fmt(data.total_expense);
  document.getElementById("netSavings").textContent = fmt(data.net_savings);
  document.getElementById("forecast").textContent = fmt(data.forecast_next_month);

  const alertBox = document.getElementById("budgetAlert");
  if (data.budget_alert) {
    alertBox.style.display = "block";
    alertBox.className = "alert-banner " + data.budget_alert.level;
    alertBox.textContent = data.budget_alert.message;
  } else {
    alertBox.style.display = "none";
  }

  renderCategoryChart(data.category_totals);
  renderTrendChart(data.months, data.monthly_income, data.monthly_expense);
}

function renderCategoryChart(categoryTotals) {
  const ctx = document.getElementById("categoryChart");
  const labels = Object.keys(categoryTotals);
  const values = Object.values(categoryTotals);

  if (categoryChart) categoryChart.destroy();
  categoryChart = new Chart(ctx, {
    type: "doughnut",
    data: {
      labels,
      datasets: [{
        data: values,
        backgroundColor: [
          "#6366f1", "#ec4899", "#f59e0b", "#10b981", "#3b82f6",
          "#ef4444", "#8b5cf6", "#14b8a6", "#f97316", "#64748b",
        ],
      }],
    },
    options: { responsive: true, plugins: { legend: { position: "right" } } },
  });
}

function renderTrendChart(months, income, expense) {
  const ctx = document.getElementById("trendChart");
  if (trendChart) trendChart.destroy();
  trendChart = new Chart(ctx, {
    type: "bar",
    data: {
      labels: months,
      datasets: [
        { label: "Income", data: income, backgroundColor: "#10b981" },
        { label: "Expense", data: expense, backgroundColor: "#ef4444" },
      ],
    },
    options: { responsive: true, scales: { y: { beginAtZero: true } } },
  });
}
