(() => {
  const refreshIcons = () => window.lucide?.createIcons();
  const coordinateIsValid = (latitude, longitude) => Number.isFinite(latitude) && Number.isFinite(longitude) && Math.abs(latitude) <= 90 && Math.abs(longitude) <= 180;
  const errorText = (widget, code) => {
    if (code === 'missing_api_key') return widget.dataset.missingKey;
    if (code === 'missing_coordinates' || code === 'invalid_coordinates') return widget.dataset.coordinateError;
    return widget.dataset.apiError;
  };
  const appendText = (parent, tag, className, value) => {
    const element = document.createElement(tag);
    if (className) element.className = className;
    element.textContent = value ?? '';
    parent.append(element);
    return element;
  };
  const iconNode = (name) => {
    const icon = document.createElement('i');
    icon.dataset.lucide = name;
    return icon;
  };

  async function loadWeather(widget, latitude, longitude, location) {
    const lat = Number(latitude);
    const lon = Number(longitude);
    const message = widget.querySelector('[data-weather-message]');
    const content = widget.querySelector('[data-weather-content]');
    const locationLabel = widget.querySelector('[data-weather-location]');
    widget._weatherRequest?.abort();
    const controller = new AbortController();
    widget._weatherRequest = controller;
    if (locationLabel && location) locationLabel.textContent = location;
    content.hidden = true;
    message.hidden = false;
    message.textContent = widget.dataset.loadingLabel || '';
    if (!coordinateIsValid(lat, lon)) {
      message.textContent = widget.dataset.coordinateError;
      return;
    }
    const url = new URL(widget.dataset.weatherEndpoint, window.location.origin);
    url.searchParams.set('lat', String(lat));
    url.searchParams.set('lon', String(lon));
    try {
      const response = await fetch(url, { headers: { Accept: 'application/json' }, signal: controller.signal });
      const data = await response.json();
      if (!response.ok || !data.available) {
        message.textContent = errorText(widget, data.error);
        return;
      }
      content.hidden = false;
      message.hidden = true;
      const sourceLabel = widget.querySelector('[data-weather-source]');
      if (sourceLabel) sourceLabel.textContent = data.source === 'open-meteo' ? 'Open-Meteo' : 'OpenWeather';
      widget.querySelector('[data-weather-condition]').textContent = data.condition;
      widget.querySelector('[data-weather-temperature]').textContent = data.temperature;
      widget.querySelector('[data-weather-feels]').textContent = data.feels_like;
      const units = { wind: 'm/s', humidity: '%', precipitation: 'mm', visibility: 'km', sunrise: '', sunset: '' };
      for (const key of Object.keys(units)) {
        const row = widget.querySelector(`[data-weather-row="${key}"]`);
        const target = widget.querySelector(`[data-weather-value="${key}"]`);
        const value = data[key];
        row.hidden = value === null || value === undefined || value === '';
        target.textContent = row.hidden ? '' : `${value}${units[key] ? ` ${units[key]}` : ''}`;
      }
      widget.querySelector('[data-weather-coordinate]').textContent = `${lat.toFixed(4)}, ${lon.toFixed(4)}`;
      const forecastMessage = widget.querySelector('[data-forecast-message]');
      forecastMessage.hidden = !data.forecast_error;
      forecastMessage.textContent = data.forecast_error ? widget.dataset.forecastError : '';
      const hourly = widget.querySelector('[data-hourly-list]');
      hourly.replaceChildren();
      for (const item of data.hourly || []) {
        const card = document.createElement('div');
        card.className = 'hourly-weather-item';
        appendText(card, 'time', '', item.time?.slice(11, 16));
        const icon = document.createElement('span');
        icon.append(iconNode(item.icon));
        card.append(icon);
        appendText(card, 'strong', '', `${item.temperature}\u00b0`);
        appendText(card, 'small', '', `${item.precipitation_probability}% \u00b7 ${item.precipitation} mm`);
        hourly.append(card);
      }
      widget.querySelector('[data-hourly-section]').hidden = !data.hourly?.length;
      const daily = widget.querySelector('[data-daily-list]');
      daily.replaceChildren();
      const language = widget.dataset.language || 'ru';
      for (const item of data.forecast || []) {
        const row = document.createElement('div');
        row.className = 'daily-weather-item';
        const date = new Date(`${item.date}T12:00:00Z`);
        appendText(row, 'span', '', new Intl.DateTimeFormat(language, { weekday: 'short', month: 'short', day: 'numeric', timeZone: 'UTC' }).format(date));
        appendText(row, 'span', '', item.condition);
        appendText(row, 'strong', '', `${item.temperature_min}\u00b0 / ${item.temperature_max}\u00b0`);
        daily.append(row);
      }
      widget.querySelector('[data-daily-section]').hidden = !data.forecast?.length;
      refreshIcons();
    } catch (error) {
      if (error.name === 'AbortError') return;
      message.hidden = false;
      content.hidden = true;
      message.textContent = widget.dataset.apiError;
    }
  }

  function drawPeak(mapComponent, peak) {
    const canvas = mapComponent.querySelector('[data-map-canvas]');
    const status = mapComponent.querySelector('[data-map-status]');
    const trailList = mapComponent.querySelector('[data-trail-list]');
    const map = canvas._mountainMap;
    const layer = canvas._mountainLayer;
    const requestId = (canvas._trailRequestId || 0) + 1;
    canvas._trailRequestId = requestId;
    const latitude = Number(peak.latitude);
    const longitude = Number(peak.longitude);
    if (!coordinateIsValid(latitude, longitude)) return;
    layer.clearLayers();
    const bounds = [];
    const peakMarker = window.L.circleMarker([latitude, longitude], {
      radius: 9, color: '#17372f', weight: 3, fillColor: '#d9f078', fillOpacity: 1,
    }).bindTooltip(`${peak.is_peak ? canvas.dataset.peakLabel : canvas.dataset.placeLabel}: ${peak.name}`, { direction: 'top' });
    peakMarker.addTo(layer);
    bounds.push([latitude, longitude]);
    map.setView([latitude, longitude], 11);
    status.textContent = canvas.dataset.loadingLabel;
    trailList.replaceChildren();
    const url = new URL(canvas.dataset.trailsEndpoint, window.location.origin);
    url.searchParams.set('lat', String(latitude));
    url.searchParams.set('lon', String(longitude));
    fetch(url, { headers: { Accept: 'application/json' } }).then(async (response) => {
      const data = await response.json();
      if (!response.ok) throw new Error(data.error || 'trails_unavailable');
      if (canvas._trailRequestId !== requestId) return;
      for (const trail of data.trails || []) {
        for (const path of trail.paths || []) {
          if (path.length < 2) continue;
          window.L.polyline(path, { color: '#b7d54a', weight: 4, opacity: 0.9 }).addTo(layer);
          bounds.push(...path);
        }
        if (trail.start) window.L.circleMarker(trail.start, { radius: 6, color: '#fff', weight: 2, fillColor: '#31584a', fillOpacity: 1 }).bindTooltip(canvas.dataset.startLabel).addTo(layer);
        if (trail.finish) window.L.circleMarker(trail.finish, { radius: 6, color: '#fff', weight: 2, fillColor: '#bd6548', fillOpacity: 1 }).bindTooltip(canvas.dataset.finishLabel).addTo(layer);
        appendText(trailList, 'li', '', trail.name || canvas.dataset.trailSegmentLabel);
      }
      if (!data.trails?.length) status.textContent = canvas.dataset.emptyLabel;
      else {
        status.textContent = `${data.trails.length} \u00b7 ${data.attribution}`;
        map.fitBounds(bounds, { padding: [24, 24], maxZoom: 14 });
      }
    }).catch((error) => {
      if (canvas._trailRequestId !== requestId) return;
      status.textContent = error.message === 'rate_limited' ? canvas.dataset.rateLabel : canvas.dataset.errorLabel;
    });
  }

  function initMap(mapComponent) {
    const canvas = mapComponent.querySelector('[data-map-canvas]');
    const status = mapComponent.querySelector('[data-map-status]');
    if (!window.L) {
      status.textContent = canvas.dataset.libraryErrorLabel;
      return;
    }
    const map = window.L.map(canvas, { scrollWheelZoom: false, zoomControl: true }).setView([20, 0], 2);
    window.L.tileLayer(canvas.dataset.tiles, { maxZoom: 19, attribution: canvas.dataset.attribution }).addTo(map);
    canvas._mountainMap = map;
    canvas._mountainLayer = window.L.layerGroup().addTo(map);
    const latitude = Number(canvas.dataset.latitude);
    const longitude = Number(canvas.dataset.longitude);
    if (coordinateIsValid(latitude, longitude)) {
      drawPeak(mapComponent, { name: canvas.dataset.peakName || canvas.dataset.peakLabel, latitude, longitude });
    } else {
      status.textContent = canvas.dataset.mapPrompt || status.textContent;
      window.setTimeout(() => map.invalidateSize(), 50);
    }
  }

  function initExplorer(explorer) {
    const form = explorer.querySelector('[data-world-search]');
    const input = explorer.querySelector('[data-world-query]');
    const status = explorer.querySelector('[data-search-status]');
    const results = explorer.querySelector('[data-search-results]');
    const selection = explorer.querySelector('[data-selected-peak]');
    const mapComponent = explorer.querySelector('.trail-map-shell');
    let foundPeaks = [];
    let searchTimer;
    let searchController;
    const search = async (query) => {
      if (query.length < 3) {
        status.textContent = explorer.dataset.minLength;
        return;
      }
      searchController?.abort();
      searchController = new AbortController();
      const url = new URL(explorer.dataset.searchEndpoint, window.location.origin);
      url.searchParams.set('q', query);
      status.textContent = explorer.dataset.searchLoading;
      results.replaceChildren();
      try {
        const response = await fetch(url, { headers: { Accept: 'application/json' }, signal: searchController.signal });
        const data = await response.json();
        if (!response.ok) throw new Error(data.error || 'search_unavailable');
        foundPeaks = data.results || [];
        if (!foundPeaks.length) {
          status.textContent = explorer.dataset.searchEmpty;
          return;
        }
        status.textContent = explorer.dataset.searchSource;
        foundPeaks.forEach((peak, index) => {
          const button = document.createElement('button');
          button.type = 'button';
          button.className = 'world-search-result';
          button.setAttribute('role', 'option');
          button.setAttribute('aria-selected', 'false');
          button.dataset.resultIndex = String(index);
          button.append(iconNode(peak.is_peak ? 'mountain' : 'map-pin'));
          const nameLocation = document.createElement('span');
          appendText(nameLocation, 'strong', '', peak.name);
          appendText(nameLocation, 'small', '', peak.location);
          button.append(nameLocation);
          if (peak.is_peak && peak.elevation !== null && peak.elevation !== undefined) appendText(button, 'span', 'result-elevation', `${peak.elevation} m`);
          button.append(iconNode('arrow-up-right'));
          results.append(button);
        });
        refreshIcons();
      } catch (error) {
        if (error.name === 'AbortError') return;
        status.textContent = error.message === 'rate_limited' ? explorer.dataset.searchRate : explorer.dataset.searchError;
      }
    };
    form.addEventListener('submit', async (event) => {
      event.preventDefault();
      window.clearTimeout(searchTimer);
      await search(input.value.trim());
    });
    input.addEventListener('input', () => {
      window.clearTimeout(searchTimer);
      const query = input.value.trim();
      if (query.length < 3) {
        searchController?.abort();
        results.replaceChildren();
        status.textContent = explorer.dataset.minLength;
        return;
      }
      searchTimer = window.setTimeout(() => search(query), 1100);
    });
    results.addEventListener('click', (event) => {
      const button = event.target.closest('[data-result-index]');
      if (!button) return;
      const peak = foundPeaks[Number(button.dataset.resultIndex)];
      if (!peak) return;
      results.querySelectorAll('[aria-selected]').forEach((item) => item.setAttribute('aria-selected', 'false'));
      button.setAttribute('aria-selected', 'true');
      selection.hidden = false;
      explorer.querySelector('[data-selected-name]').textContent = peak.name;
      explorer.querySelector('[data-selected-location]').textContent = peak.location;
      const elevation = explorer.querySelector('.selected-peak-elevation');
      elevation.hidden = !peak.is_peak;
      explorer.querySelector('[data-selected-elevation]').textContent = peak.elevation === null || peak.elevation === undefined ? explorer.dataset.elevationMissing : `${peak.elevation} m`;
      explorer.querySelector('[data-selected-coordinates]').textContent = `${Number(peak.latitude).toFixed(5)}, ${Number(peak.longitude).toFixed(5)}`;
      input.value = peak.name;
      const canvas = mapComponent.querySelector('[data-map-canvas]');
      canvas.dataset.latitude = String(peak.latitude);
      canvas.dataset.longitude = String(peak.longitude);
      drawPeak(mapComponent, peak);
      window.requestAnimationFrame(() => canvas._mountainMap.invalidateSize({ pan: false }));
      loadWeather(explorer.querySelector('[data-weather-widget]'), peak.latitude, peak.longitude, peak.name);
      selection.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
    });
  }

  function initPreparePlaceSearch(widget) {
    const input = widget.querySelector('[data-place-query]');
    const button = widget.querySelector('[data-place-submit]');
    const status = widget.querySelector('[data-place-status]');
    const results = widget.querySelector('[data-place-results]');
    const hiddenValue = widget.querySelector('[data-place-value]');
    const card = widget.querySelector('[data-place-card]');
    const trailSection = widget.querySelector('[data-place-trails-section]');
    const searchUrl = new URL(widget.dataset.searchEndpoint, window.location.origin);
    const trailsUrl = new URL(widget.dataset.trailsEndpoint, window.location.origin);
    let searchController;
    let trailsController;
    let requestId = 0;

    const renderPlace = (place, isSearchResult = false) => {
      hiddenValue.value = place.name || '';
      input.value = place.name || '';
      card.hidden = false;
      widget.querySelector('[data-place-name]').textContent = place.name || '';
      widget.querySelector('[data-place-location]').textContent = place.location || place.display_name || '—';
      widget.querySelector('[data-place-coordinates]').textContent = `${Number(place.latitude).toFixed(5)}, ${Number(place.longitude).toFixed(5)}`;
      const elevationRow = widget.querySelector('[data-place-elevation-row]');
      elevationRow.hidden = place.elevation === null || place.elevation === undefined || place.elevation === '';
      widget.querySelector('[data-place-elevation]').textContent = elevationRow.hidden ? '' : `${place.elevation} m`;
      widget.querySelector('[data-place-type]').textContent = [place.category, place.kind].filter(Boolean).join(' · ') || '—';
      const detail = place.description || place.display_name || `${place.kind || 'Place'} · OpenStreetMap`;
      widget.querySelector('[data-place-description]').textContent = detail;
      results.replaceChildren();
      results.hidden = true;
      input.setCustomValidity('');
      trailsController?.abort();
      loadNearbyTrails(place, requestId);
      if (isSearchResult) refreshIcons();
    };

    const clearSelection = () => {
      hiddenValue.value = '';
      card.hidden = true;
      trailSection.hidden = true;
      widget.querySelector('[data-place-trails]').replaceChildren();
    };

    async function loadNearbyTrails(place, selectedRequest) {
      const latitude = Number(place.latitude);
      const longitude = Number(place.longitude);
      if (!coordinateIsValid(latitude, longitude)) { trailSection.hidden = true; return; }
      trailsController?.abort();
      trailsController = new AbortController();
      const trailStatus = widget.querySelector('[data-place-trails-status]');
      const trailList = widget.querySelector('[data-place-trails]');
      trailSection.hidden = false;
      trailList.replaceChildren();
      trailStatus.textContent = widget.dataset.trailsLoading;
      const url = new URL(trailsUrl);
      url.searchParams.set('lat', String(latitude));
      url.searchParams.set('lon', String(longitude));
      try {
        const response = await fetch(url, { headers: { Accept: 'application/json' }, signal: trailsController.signal });
        const data = await response.json();
        if (selectedRequest !== requestId) return;
        if (!response.ok) throw new Error(data.error || 'trails_unavailable');
        const trails = data.trails || [];
        trailStatus.textContent = trails.length ? `${trails.length} · ${data.attribution || 'OpenStreetMap'}` : widget.dataset.noTrailsLabel;
        trails.forEach((trail) => appendText(trailList, 'li', '', trail.name || widget.dataset.trailsLabel));
      } catch (error) {
        if (error.name === 'AbortError' || selectedRequest !== requestId) return;
        trailStatus.textContent = error.message === 'rate_limited' ? widget.dataset.rateLabel : widget.dataset.trailsError;
      }
    }

    async function search() {
      const query = input.value.trim();
      const currentRequest = ++requestId;
      searchController?.abort();
      if (query.length < 3) { status.textContent = widget.dataset.minLabel; return; }
      searchController = new AbortController();
      clearSelection();
      results.replaceChildren();
      status.textContent = widget.dataset.loadingLabel;
      button.disabled = true;
      try {
        const url = new URL(searchUrl);
        url.searchParams.set('q', query);
        const response = await fetch(url, { headers: { Accept: 'application/json' }, signal: searchController.signal });
        const data = await response.json();
        if (currentRequest !== requestId) return;
        if (!response.ok) throw new Error(data.error || 'search_unavailable');
        const places = data.results || [];
        if (!places.length) { status.textContent = widget.dataset.emptyLabel; return; }
        status.textContent = `${places.length} · ${data.source || 'OpenStreetMap'}`;
        places.forEach((place, index) => {
          const result = document.createElement('button');
          result.type = 'button';
          result.className = 'prepare-place-result';
          result.setAttribute('role', 'option');
          result.setAttribute('aria-selected', 'false');
          result.dataset.placeIndex = String(index);
          result.append(iconNode(place.is_peak ? 'mountain' : 'map-pin'));
          const text = document.createElement('span');
          appendText(text, 'strong', '', place.name);
          appendText(text, 'small', '', place.location || place.display_name || '');
          result.append(text);
          const meta = document.createElement('span');
          meta.className = 'prepare-place-result-meta';
          appendText(meta, 'strong', '', place.elevation ? `${place.elevation} m` : (place.kind || ''));
          appendText(meta, 'small', '', `${Number(place.latitude).toFixed(3)}, ${Number(place.longitude).toFixed(3)}`);
          result.append(meta);
          results.append(result);
          result._place = place;
        });
        results.hidden = false;
        refreshIcons();
      } catch (error) {
        if (error.name === 'AbortError' || currentRequest !== requestId) return;
        status.textContent = error.message === 'rate_limited' ? widget.dataset.rateLabel : widget.dataset.errorLabel;
      } finally {
        if (currentRequest === requestId) button.disabled = false;
      }
    }

    button.addEventListener('click', search);
    input.addEventListener('keydown', (event) => {
      if (event.key === 'Enter') { event.preventDefault(); search(); }
      if (event.key === 'Escape') results.hidden = true;
    });
    input.addEventListener('input', () => {
      requestId += 1;
      searchController?.abort();
      button.disabled = false;
      clearSelection();
      results.hidden = true;
      status.textContent = widget.dataset.minLabel;
    });
    results.addEventListener('click', (event) => {
      const result = event.target.closest('[data-place-index]');
      if (!result?._place) return;
      results.querySelectorAll('[aria-selected]').forEach((item) => item.setAttribute('aria-selected', 'false'));
      result.setAttribute('aria-selected', 'true');
      requestId += 1;
      renderPlace(result._place, true);
      status.textContent = '';
      card.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
    });
    widget.querySelector('[data-place-clear]')?.addEventListener('click', () => {
      requestId += 1;
      trailsController?.abort();
      input.value = '';
      clearSelection();
      status.textContent = widget.dataset.minLabel;
      input.focus();
    });
    widget.closest('form')?.addEventListener('submit', (event) => {
      if (!hiddenValue.value.trim()) {
        event.preventDefault();
        input.setCustomValidity(widget.dataset.selectLabel);
        input.reportValidity();
        input.focus();
      }
    });

    try {
      const initial = JSON.parse(document.getElementById('prepare-initial-place')?.textContent || 'null');
      if (initial) { requestId += 1; renderPlace(initial); status.textContent = ''; }
      else if (hiddenValue.value) input.value = hiddenValue.value;
    } catch { /* No preselected place. */ }
  }

  document.addEventListener('DOMContentLoaded', () => {
    document.querySelectorAll('[data-prepare-place-search]').forEach(initPreparePlaceSearch);
    document.querySelectorAll('[data-mountain-filter]').forEach((input) => {
      const form = input.closest('form');
      const selectedMountain = form?.querySelector('[data-selected-mountain]');
      const options = input.list?.querySelectorAll('option') || [];
      if (!selectedMountain || !options.length) return;
      input.addEventListener('input', () => {
        const value = input.value.trim().toLocaleLowerCase();
        const match = [...options].find((option) => option.value.toLocaleLowerCase() === value);
        selectedMountain.value = match?.dataset.id || '';
        input.setCustomValidity(match ? '' : 'Выберите гору из списка');
      });
    });
    document.querySelectorAll('[data-gear-filter]').forEach((input) => {
      const list = input.closest('.gear-panel')?.querySelector('[data-gear-list]');
      if (!list) return;
      const empty = input.closest('.gear-panel').querySelector('[data-gear-empty]');
      input.addEventListener('input', () => {
        const query = input.value.trim().toLocaleLowerCase();
        let matches = 0;
        list.querySelectorAll('.gear-group').forEach((group) => {
          let visibleItems = 0;
          group.querySelectorAll('.gear-row').forEach((row) => {
            const visible = row.textContent.toLocaleLowerCase().includes(query);
            row.hidden = !visible;
            if (visible) {
              visibleItems += 1;
              matches += 1;
            }
          });
          group.hidden = visibleItems === 0;
        });
        if (empty) empty.hidden = matches !== 0;
      });
    });
    document.querySelectorAll('[data-check-progress]').forEach((progress) => {
      const panel = progress.closest('.prep-layout')?.querySelector('.gear-panel');
      if (!panel) return;
      const rows = [...panel.querySelectorAll('.gear-row')];
      const label = progress.querySelector('[data-progress-label]');
      const count = progress.querySelector('[data-progress-count]');
      const bar = progress.querySelector('[data-progress-bar]');
      const track = progress.querySelector('[role="progressbar"]');
      const update = () => {
        const ready = rows.filter((row) => row.querySelector('input[value="have"]:checked')).length;
        const percent = rows.length ? Math.round((ready / rows.length) * 100) : 0;
        if (label) label.textContent = `${percent}%`;
        if (count) count.textContent = `${ready} / ${rows.length}`;
        if (bar) bar.style.width = `${percent}%`;
        if (track) track.setAttribute('aria-valuenow', String(percent));
      };
      panel.addEventListener('change', update);
      update();
    });
    document.querySelectorAll('[data-weather-widget]').forEach((widget) => {
      if (widget.dataset.latitude && widget.dataset.longitude) {
        loadWeather(widget, widget.dataset.latitude, widget.dataset.longitude, widget.dataset.location);
      } else {
        const message = widget.querySelector('[data-weather-message]');
        message.textContent = widget.dataset.coordinateError;
      }
    });
    document.querySelectorAll('[data-place-search]').forEach((form) => {
      const input = form.querySelector('input[name="q"]');
      const status = form.querySelector('[data-place-status]');
      const button = form.querySelector('button[type="submit"]');
      const messages = {
        ru: { loading: '\u0418\u0449\u0435\u043c \u043c\u0435\u0441\u0442\u043e\u2026', empty: '\u041d\u0438\u0447\u0435\u0433\u043e \u043d\u0435 \u043d\u0430\u0439\u0434\u0435\u043d\u043e. \u0423\u0442\u043e\u0447\u043d\u0438\u0442\u0435 \u043d\u0430\u0437\u0432\u0430\u043d\u0438\u0435 \u0433\u043e\u0440\u043e\u0434\u0430.', error: '\u041f\u043e\u0438\u0441\u043a \u043c\u0435\u0441\u0442\u0430 \u0432\u0440\u0435\u043c\u0435\u043d\u043d\u043e \u043d\u0435\u0434\u043e\u0441\u0442\u0443\u043f\u0435\u043d.', rate: '\u041f\u043e\u0434\u043e\u0436\u0434\u0438\u0442\u0435 \u043c\u0438\u043d\u0443\u0442\u0443 \u0438 \u043f\u043e\u043f\u0440\u043e\u0431\u0443\u0439\u0442\u0435 \u0441\u043d\u043e\u0432\u0430.' },
        kk: { loading: '\u041e\u0440\u044b\u043d \u0456\u0437\u0434\u0435\u043b\u0443\u0434\u0435\u2026', empty: '\u041e\u0440\u044b\u043d \u0442\u0430\u0431\u044b\u043b\u043c\u0430\u0434\u044b. \u049a\u0430\u043b\u0430 \u0430\u0442\u0430\u0443\u044b\u043d \u043d\u0430\u049b\u0442\u044b\u043b\u0430\u04a3\u044b\u0437.', error: '\u041e\u0440\u044b\u043d\u0434\u044b \u0456\u0437\u0434\u0435\u0443 \u0443\u0430\u049b\u044b\u0442\u0448\u0430 \u049b\u043e\u043b\u0436\u0435\u0442\u0456\u043c\u0441\u0456\u0437.', rate: '\u0411\u0456\u0440 \u043c\u0438\u043d\u0443\u0442 \u043a\u04af\u0442\u0456\u043f, \u049b\u0430\u0439\u0442\u0430\u0434\u0430\u043d \u043a\u04e9\u0440\u0456\u04a3\u0456\u0437.' },
        en: { loading: 'Searching for the place…', empty: 'No place found. Try a more specific city name.', error: 'Place search is temporarily unavailable.', rate: 'Wait a moment and try again.' },
      };
      const language = (document.documentElement.lang || 'en').slice(0, 2);
      const copy = messages[language] || messages.en;
      form.addEventListener('submit', async (event) => {
        event.preventDefault();
        const query = input.value.trim();
        if (query.length < 2) return;
        button.disabled = true;
        status.textContent = copy.loading;
        try {
          const url = new URL(form.dataset.endpoint, window.location.origin);
          url.searchParams.set('q', query);
          const response = await fetch(url, { headers: { Accept: 'application/json' } });
          const data = await response.json();
          const place = data.results?.[0];
          if (!response.ok) {
            status.textContent = data.error === 'rate_limited' ? copy.rate : copy.error;
          } else if (!place) {
            status.textContent = copy.empty;
          } else {
            status.textContent = '';
            const widget = form.closest('.weather-main').querySelector('[data-weather-widget]');
            loadWeather(widget, place.latitude, place.longitude, place.name);
          }
        } catch {
          status.textContent = copy.error;
        } finally {
          button.disabled = false;
        }
      });
    });
    document.querySelectorAll('[data-map-canvas]').forEach((map) => initMap(map.closest('.trail-map-shell')));
    document.querySelectorAll('[data-mountain-explorer]').forEach(initExplorer);
  });
})();
