document.addEventListener('DOMContentLoaded', () => {

  // --- Configuration ---
  const STEPS = ['step-1', 'step-2', 'step-3', 'step-4'];
  const REQUIREMENTS = {
    'ingredients': ['name', 'cost_per_unit', 'unit', 'par_level'],
    'menu': ['name', 'price'],
    'recipes': ['menu_item', 'ingredient', 'quantity'],
    'sales': ['date', 'menu_item', 'quantity']
  };

  // --- State Management ---
  checkStatus();

  // --- Event Listeners ---

  // City Input (Prologue)
  const cityInput = document.getElementById('city-input');
  let cityTimeout;
  cityInput.addEventListener('input', (e) => {
    const city = e.target.value;
    if (cityTimeout) clearTimeout(cityTimeout);
    cityTimeout = setTimeout(() => checkWeather(city), 800);
  });

  // Dropzones
  setupDropzone('ingredients', REQUIREMENTS['ingredients']);
  setupDropzone('menu', REQUIREMENTS['menu']);
  setupDropzone('recipes', REQUIREMENTS['recipes']);
  setupDropzone('sales', REQUIREMENTS['sales']);

  // Calibration (Magic)
  document.getElementById('btn-calibrate').addEventListener('click', startCalibration);

  // --- Functions ---

  async function checkStatus() {
    try {
      const res = await fetch('/onboarding/api/status');
      const status = await res.json();

      // Unlock steps based on status
      if (status.ingredients) markCompleted('step-1');
      if (status.menu) markCompleted('step-2');
      if (status.recipes) markCompleted('step-3');
      if (status.sales) markCompleted('step-4');

      // Unlock next logical step
      if (!status.ingredients) unlock('step-1');
      else if (!status.menu) unlock('step-2');
      else if (!status.recipes) unlock('step-3');
      else if (!status.sales) unlock('step-4');
      else {
        // All done -> Unlock Magic
        document.getElementById('btn-calibrate').disabled = false;
        document.getElementById('step-magic').style.opacity = '1';
        document.getElementById('step-magic').style.pointerEvents = 'all';
      }

    } catch (e) {
      console.error("Status check failed", e);
    }
  }

  async function checkWeather(city) {
    if (!city || city.length < 3) return;
    const msg = document.getElementById('weather-msg');
    msg.textContent = "Checking satellites...";
    msg.className = "input-message"; // reset

    try {
      const res = await fetch(`/onboarding/api/weather?city=${city}`);
      const data = await res.json();

      msg.textContent = data.message;
      if (data.available) {
        msg.classList.add('success');
        // Auto-save city coordinates implied here (mocked for now)
      } else {
        msg.classList.add('error'); // Or just neutral as per design -> "Note:"
      }
    } catch (e) {
      msg.textContent = "Weather service unreachable.";
      msg.classList.add('error');
    }
  }

  function setupDropzone(type, requiredCols) {
    const zone = document.getElementById(`drop-${type}`);
    const fileInput = document.createElement('input');
    fileInput.type = 'file';
    fileInput.accept = '.csv';
    fileInput.style.display = 'none';
    zone.appendChild(fileInput);

    zone.addEventListener('click', () => fileInput.click());

    fileInput.addEventListener('change', (e) => {
      if (e.target.files.length > 0) processFile(e.target.files[0], type, requiredCols);
    });

    // Drag & Drop visual omitted for brevity, standard events work
  }

  function processFile(file, type, requiredCols) {
    Papa.parse(file, {
      header: true,
      preview: 1, // Only read first row for headers
      complete: function (results) {
        const headers = results.meta.fields;
        const missing = requiredCols.filter(col => !headers.includes(col));

        if (missing.length > 0) {
          // Trigger Mapping Modal
          showMappingModal(file, type, headers, requiredCols);
        } else {
          // Direct Upload
          uploadFile(file, type, null);
        }
      }
    });
  }

  function showMappingModal(file, type, fileHeaders, requiredCols) {
    const modal = document.getElementById('mapping-modal');
    const container = document.getElementById('mapping-container');
    container.innerHTML = ''; // Clear previous

    requiredCols.forEach(req => {
      // Check if matches exactly?
      const exactMatch = fileHeaders.find(h => h === req);

      const row = document.createElement('div');
      row.className = 'mapping-row';

      const label = document.createElement('div');
      label.textContent = `Req: ${req}`;
      label.style.fontWeight = '600';

      const select = document.createElement('select');
      select.dataset.target = req;

      // Option for Select
      const defOpt = document.createElement('option');
      defOpt.text = '-- Select Column --';
      defOpt.value = '';
      select.appendChild(defOpt);

      fileHeaders.forEach(h => {
        const opt = document.createElement('option');
        opt.value = h;
        opt.text = h;
        if (h === req) opt.selected = true; // Auto-select matches
        select.appendChild(opt);
      });

      row.appendChild(label);
      row.appendChild(select);
      container.appendChild(row);
    });

    modal.style.display = 'flex';

    const confirmBtn = document.getElementById('btn-confirm-mapping');
    // Clean old listeners
    const newBtn = confirmBtn.cloneNode(true);
    confirmBtn.parentNode.replaceChild(newBtn, confirmBtn);

    newBtn.addEventListener('click', () => {
      // Build Mapping JSON
      const mapping = {};
      const selects = container.querySelectorAll('select');
      let valid = true;

      selects.forEach(sel => {
        if (!sel.value) valid = false;
        mapping[sel.dataset.target] = sel.value;
      });

      if (!valid) {
        alert("Please map all columns.");
        return;
      }

      modal.style.display = 'none';
      uploadFile(file, type, mapping);
    });
  }

  async function uploadFile(file, type, mapping) {
    const formData = new FormData();
    formData.append('file', file);
    if (mapping) {
      formData.append('mapping', JSON.stringify(mapping));
    }

    const msgBox = document.getElementById(`msg-${type}`);
    msgBox.textContent = "Validating...";
    msgBox.className = 'input-message';

    try {
      const res = await fetch(`/onboarding/api/validate/${type}`, {
        method: 'POST',
        body: formData
      });
      const data = await res.json();

      if (data.valid) {
        msgBox.textContent = `Success! ${data.count} records verified.`;
        msgBox.classList.add('success');
        markCompleted(`step-${getNextStepIndex(type)}`); // Hacky index mapping

        // Refresh status to unlock next
        checkStatus();
      } else {
        msgBox.textContent = `Error: ${data.error}`;
        msgBox.classList.add('error');
      }
    } catch (e) {
      msgBox.textContent = "Upload failed.";
      msgBox.classList.add('error');
    }
  }

  function getNextStepIndex(type) {
    if (type === 'ingredients') return 1;
    if (type === 'menu') return 2;
    if (type === 'recipes') return 3;
    if (type === 'sales') return 4;
    return 0;
  }

  function unlock(id) {
    const el = document.getElementById(id);
    if (el) {
      el.classList.add('active');
      el.classList.remove('completed');
    }
  }

  function markCompleted(id) {
    const el = document.getElementById(id);
    if (el) {
      el.classList.add('completed');
      el.classList.add('active'); // Ensure visible
    }
  }

  function startCalibration() {
    const log = document.getElementById('discovery-log');
    log.style.display = 'block';
    log.innerHTML = '';
    const btn = document.getElementById('btn-calibrate');
    btn.disabled = true;
    btn.textContent = "Running Intelligence Engine...";

    const evtSource = new EventSource("/onboarding/api/stream");

    evtSource.onmessage = function (event) {
      const div = document.createElement('div');
      div.className = 'log-entry';
      div.textContent = `> ${event.data}`;
      log.appendChild(div);
      log.scrollTop = log.scrollHeight;
    };

    evtSource.onerror = function () {
      evtSource.close();
    };

    // Here we would also trigger the backend task via POST if not already running
    // But for this simulation, we assume the stream connects to info.
  }

});
