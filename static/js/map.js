document.addEventListener("DOMContentLoaded", () => {
  let currentTab = 'users';
  let countryData = {users: {}, papers: {}};

  async function loadCountryData() {
    try {
      const [usersResponse, papersResponse] = await Promise.all([
        fetch('/api/countries-with-users'),
        fetch('/api/countries-with-papers')
      ]);

      countryData.users = await usersResponse.json();
      countryData.papers = await papersResponse.json();

      updateMapColors();
    } catch (err) {
      console.error("Failed to load country data:", err);
    }
  }

  function updateMapColors() {
    const countries = document.querySelectorAll("path.land");
    const activeData = countryData[currentTab];

    countries.forEach(country => {
      const countryCode = country.id;
      country.classList.remove("has-data", "selected");

      if (activeData[countryCode] && activeData[countryCode].length > 0) {
        country.classList.add("has-data");
      }
    });
  }

  document.getElementById("toggle-users").addEventListener("click", () => {
    currentTab = 'users';
    document.querySelectorAll('.toggle-btn').forEach(btn => btn.classList.remove('selected'));
    document.getElementById("toggle-users").classList.add('selected');
    updateMapColors();
    clearCountryDetails();
  });

  document.getElementById("toggle-papers").addEventListener("click", () => {
    currentTab = 'papers';
    document.querySelectorAll('.toggle-btn').forEach(btn => btn.classList.remove('selected'));
    document.getElementById("toggle-papers").classList.add('selected');
    updateMapColors();
    clearCountryDetails();
  });

  const countries = document.querySelectorAll("path.land");
  countries.forEach(country => {
    country.addEventListener("click", async () => {
      countries.forEach(c => c.classList.remove("selected"));
      country.classList.add("selected");

      const countryCode = country.id;
      const countryName = country.getAttribute("title") || countryCode;

      showCountryDetails(countryCode, countryName);
    });
  });

  function showCountryDetails(countryCode, countryName) {
    const activeData = countryData[currentTab];
    const items = activeData[countryCode] || [];

    let displayDiv = document.getElementById('display-items');
    displayDiv.innerHTML = '';

    if (items.length === 0) {
      displayDiv.innerHTML = `
      <h2 class="title text-center" style="font-size:2rem">${currentTab === 'users' ? 'Users' : 'Discussion Papers'} in ${countryName}</h2>
      <div class="text-center">
        There are no ${currentTab === 'users' ? 'users' : 'discussion papers'} based in ${countryName}.
      </div>
    `;
      return;
    }

    let listHtml = '<div class="list-group">';
    const top5 = items.slice(0, 5);
    top5.forEach(item => {
      if (currentTab === 'users') {
        listHtml += `
        <div class="list-group-item list-group-item-action" style="margin-bottom: 0">
          <div class="d-flex w-100 justify-content-between">
            <h3 class="list-title">${item.first_name} ${item.last_name}</h3>
          </div>
          <p class="list-description">${item.position}</p>
        </div>
      `;
      } else {
        listHtml += `
        <div class="list-group-item list-group-item-action" style="margin-bottom: 0">
          <div class="d-flex w-100 justify-content-between">
            <h3 class="list-title">${item.title}</h3>
          </div>
          <p class="list-description">${item.author || 'Unknown Author'}</p>
        </div>
      `;
      }
    });
    listHtml += '</div>';

    let moreLink = '';
    if (items.length > 5) {
      moreLink = `
      <a href="/${currentTab}/country/${countryCode}" class="btn btn-link p-0 mt-2">
        See more...
      </a>
    `;
    }

    displayDiv.innerHTML = `
    <h2 class="title text-center" style="font-size:2rem">${currentTab === 'users' ? 'Users' : 'Discussion Papers'} in ${countryName}</h2>
    ${listHtml}
    ${moreLink}
  `;
  }

  function clearCountryDetails() {
    const existingDetails = document.getElementById('display-items');
    if (existingDetails) {
      existingDetails.innerHTML = '';
    }
  }

  loadCountryData();
});
