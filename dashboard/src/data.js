/* ============================================================
   TAP — live data layer
   Fetches from the occupancy API and populates window.TAP_DATA
   in the same shape that the design-file components expect.

   Falls back to deterministic mock data if the API is unavailable
   (e.g. during development without a running server).
   ============================================================ */

(function () {
  'use strict';

  // ---- Helpers -------------------------------------------------------
  function urlMonth() {
    const p = new URLSearchParams(window.location.search);
    const m = p.get('month');
    if (m && /^\d{4}-(0[1-9]|1[0-2])$/.test(m)) return m;
    const now = new Date();
    return now.getFullYear() + '-' + String(now.getMonth() + 1).padStart(2, '0');
  }

  function prevMonthStr(m) {
    const [y, mo] = m.split('-').map(Number);
    const d = new Date(Date.UTC(y, mo - 2, 1));   // mo-1 is current, mo-2 is previous
    return d.getUTCFullYear() + '-' + String(d.getUTCMonth() + 1).padStart(2, '0');
  }

  function daysInMonthStr(m) {
    const [y, mo] = m.split('-').map(Number);
    return new Date(Date.UTC(y, mo, 0)).getUTCDate();
  }

  function monthStartDate(m) {
    const [y, mo] = m.split('-').map(Number);
    return new Date(Date.UTC(y, mo - 1, 1));
  }

  function monthEndDate(m) {
    const [y, mo] = m.split('-').map(Number);
    const days = daysInMonthStr(m);
    return new Date(Date.UTC(y, mo - 1, days));
  }

  // ---- Live API fetch ------------------------------------------------
  function fetchWithTimeout(url, ms) {
    return Promise.race([
      fetch(url),
      new Promise(function (_, reject) {
        setTimeout(function () { reject(new Error('fetch timeout: ' + url)); }, ms);
      }),
    ]);
  }

  var _FETCH_TIMEOUT_MS = 6000;

  async function fetchAllData(month) {
    const prev = prevMonthStr(month);
    const responses = await Promise.all([
      fetchWithTimeout('/api/occupancy/properties?month=' + month, _FETCH_TIMEOUT_MS),
      fetchWithTimeout('/api/occupancy/properties?month=' + prev, _FETCH_TIMEOUT_MS),
      fetchWithTimeout('/api/occupancy/units-monthly?month=' + month, _FETCH_TIMEOUT_MS),
      fetchWithTimeout('/api/occupancy/data-quality', _FETCH_TIMEOUT_MS),
      fetchWithTimeout('/api/occupancy/settings/target', _FETCH_TIMEOUT_MS),
    ]);

    // properties is required; others are best-effort
    if (!responses[0].ok) {
      throw new Error('Properties API returned ' + responses[0].status);
    }

    const [propsData, propsPrevData, unitsData, dqData, targetsData] = await Promise.all(
      responses.map((r, i) => {
        if (!r.ok) return i === 0 ? Promise.reject(new Error('status ' + r.status)) : Promise.resolve(null);
        return r.json();
      })
    );

    return { propsData, propsPrevData, unitsData, dqData, targetsData };
  }

  // ---- Transform: API → window.TAP_DATA shape ------------------------
  function buildTapData(apiData, month) {
    const { propsData, propsPrevData, unitsData, dqData, targetsData } = apiData;

    const TODAY = new Date();
    const TODAY_DAY = TODAY.getDate();
    const DAYS = daysInMonthStr(month);
    const MONTH_START = monthStartDate(month);
    const MONTH_END = monthEndDate(month);

    // Previous-month ops rate lookup
    const prevRateMap = {};
    if (propsPrevData && propsPrevData.properties) {
      for (const p of propsPrevData.properties) {
        prevRateMap[p.propertyId] = p.opsRate / 100;
      }
    }

    // Target map from settings API
    const targetMap = {};
    if (targetsData && targetsData.targets) {
      for (const t of targetsData.targets) {
        targetMap[t.propertyId] = t.targetRate / 100;
      }
    }

    // PROPERTIES
    const PROPERTIES = propsData.properties.map(function (p) {
      return {
        id: p.propertyId,
        name: p.propertyName,
        type: p.propertyType,
        region: p.region || 'N/A',
        units: p.available,
        target: targetMap[p.propertyId] != null ? targetMap[p.propertyId] : (p.targetRate / 100),
      };
    });

    // UNITS — from units-monthly endpoint
    const UNITS = [];
    if (unitsData && unitsData.units) {
      for (const u of unitsData.units) {
        UNITS.push({
          id: u.unit_id,
          propertyId: u.property_id,
          label: u.unit_name,
          kind: u.unit_type,
          floor: _parseFloor(u.unit_name),
          days: u.days || new Array(DAYS).fill(false),
          status: u.status,
          tenant: u.tenant_name || null,
          leaseStart: u.lease_start || null,
          leaseEnd: u.lease_end || null,
          moveIn: u.move_in || null,
          moveOut: u.move_out || null,
          daysVacant: u.days_vacant || 0,
          upcomingMoveOut: u.upcoming_move_out || false,
          notes: '',
          dqFlags: u.dq_flags || [],
          nextAvailable: u.next_available || null,
          crmLink: u.crm_link || null,
        });
      }
    }

    // PROPERTY_STATS
    const PROPERTY_STATS = propsData.properties.map(function (p) {
      const prop = PROPERTIES.find(function (pr) { return pr.id === p.propertyId; });
      const prevRate = prevRateMap[p.propertyId] || 0;

      const daily = (p.dailySeries || []).map(function (d) {
        const dayNum = new Date(d.date + 'T00:00:00Z').getUTCDate();
        return { day: dayNum, occ: d.occupied, total: d.available, rate: d.rate / 100 };
      });
      // Pad to full month if the series is shorter (e.g. future days missing)
      while (daily.length < DAYS) {
        daily.push({ day: daily.length + 1, occ: 0, total: p.available || 1, rate: 0 });
      }

      return {
        property: prop,
        units: p.available,
        occupied: p.occupied || 0,
        vacant: p.vacant || 0,
        reserved: p.reserved || 0,
        maintenance: p.maintenance || 0,
        financeOccCount: p.financeOccCount != null
          ? p.financeOccCount
          : Math.round(p.financeRate * p.available / 100),
        financeRate: p.financeRate / 100,
        opsRate: p.opsRate / 100,
        opsRatePrev: prevRate,
        delta: p.opsRate / 100 - prevRate,
        moveIns: p.moveIns || 0,
        moveOuts: p.moveOuts || 0,
        daily: daily,
        lastUpdated: p.lastUpdated || 'recently',
      };
    });

    // PORTFOLIO — aggregate from PROPERTY_STATS
    const totalUnits = PROPERTY_STATS.reduce(function (a, s) { return a + s.units; }, 0) || 1;
    const dailyAgg = [];
    for (let d = 0; d < DAYS; d++) {
      let occ = 0, tot = 0;
      PROPERTY_STATS.forEach(function (s) {
        if (s.daily[d]) { occ += s.daily[d].occ; tot += s.daily[d].total; }
      });
      dailyAgg.push({ day: d + 1, occ: occ, total: tot || 1, rate: tot ? occ / tot : 0 });
    }
    const opsRate = dailyAgg.reduce(function (a, d) { return a + d.rate; }, 0) / DAYS;
    const prevAvg = PROPERTY_STATS.reduce(function (a, s) {
      return a + s.opsRatePrev * s.units;
    }, 0) / totalUnits;

    const sortedDays = dailyAgg.slice().sort(function (a, b) { return b.rate - a.rate; });
    const todayIdx = Math.max(0, Math.min(TODAY_DAY - 1, DAYS - 1));

    const PORTFOLIO = {
      totalUnits: totalUnits,
      occupied: PROPERTY_STATS.reduce(function (a, s) { return a + s.occupied; }, 0),
      vacant: PROPERTY_STATS.reduce(function (a, s) { return a + s.vacant; }, 0),
      reserved: PROPERTY_STATS.reduce(function (a, s) { return a + s.reserved; }, 0),
      maintenance: PROPERTY_STATS.reduce(function (a, s) { return a + s.maintenance; }, 0),
      moveIns: PROPERTY_STATS.reduce(function (a, s) { return a + s.moveIns; }, 0),
      moveOuts: PROPERTY_STATS.reduce(function (a, s) { return a + s.moveOuts; }, 0),
      financeOccCount: PROPERTY_STATS.reduce(function (a, s) { return a + s.financeOccCount; }, 0),
      financeRate: PROPERTY_STATS.reduce(function (a, s) { return a + s.financeOccCount; }, 0) / totalUnits,
      opsRate: opsRate,
      opsRatePrev: prevAvg,
      delta: opsRate - prevAvg,
      dailyAgg: dailyAgg,
      highest: sortedDays[0] || { day: 1, rate: 0 },
      lowest: sortedDays[sortedDays.length - 1] || { day: 1, rate: 0 },
      todayRate: dailyAgg[todayIdx] ? dailyAgg[todayIdx].rate : 0,
      belowTarget: PROPERTY_STATS.filter(function (s) {
        return s.opsRate < s.property.target;
      }).length,
    };

    // INSIGHTS
    const INSIGHTS = _buildInsights(PROPERTY_STATS, UNITS);

    // DATA_QUALITY
    const DATA_QUALITY = _buildDataQuality(dqData);

    window.TAP_DATA = {
      TODAY: TODAY,
      MONTH_START: MONTH_START,
      MONTH_END: MONTH_END,
      DAYS_IN_MONTH: DAYS,
      TODAY_DAY: TODAY_DAY,
      PROPERTIES: PROPERTIES,
      UNITS: UNITS,
      PROPERTY_STATS: PROPERTY_STATS,
      PORTFOLIO: PORTFOLIO,
      INSIGHTS: INSIGHTS,
      DATA_QUALITY: DATA_QUALITY,
      helpers: {},
      usingMock: false,
    };
  }

  function _parseFloor(unitName) {
    // Try to extract floor number from common patterns like "A-304" → floor 3
    // or "Floor 2" → 2
    if (!unitName) return 1;
    var m = unitName.match(/floor\s*(\d+)/i);
    if (m) return parseInt(m[1], 10);
    m = unitName.match(/-(\d)(\d{2})$/);
    if (m) return parseInt(m[1], 10);
    return 1;
  }

  function _buildInsights(stats, units) {
    var insights = [];

    var below = stats.filter(function (s) { return s.opsRate < s.property.target; });
    if (below.length) {
      insights.push({
        severity: below.some(function (s) { return (s.property.target - s.opsRate) > 0.10; }) ? 'bad' : 'warn',
        kind: 'below-target',
        title: below.length + ' ' + (below.length === 1 ? 'property' : 'properties') + ' below target',
        detail: below.slice(0, 3).map(function (s) {
          return s.property.name + ' — ' + (s.opsRate * 100).toFixed(0) + '% / ' + (s.property.target * 100).toFixed(0) + '% target';
        }).join(' · '),
        count: below.length,
        propertyIds: below.map(function (s) { return s.property.id; }),
      });
    }

    var vac14 = units.filter(function (u) {
      return (u.status === 'vacant' || u.status === 'maintenance') && u.daysVacant > 14 && u.daysVacant <= 30;
    });
    if (vac14.length) {
      insights.push({ severity: 'warn', kind: 'vacant-14',
        title: vac14.length + ' units vacant 14+ days',
        detail: 'Listings may need refresh — rent or photo update.', count: vac14.length });
    }

    var vac30 = units.filter(function (u) {
      return (u.status === 'vacant' || u.status === 'maintenance') && u.daysVacant > 30;
    });
    if (vac30.length) {
      insights.push({ severity: 'bad', kind: 'vacant-30',
        title: vac30.length + ' units vacant 30+ days',
        detail: 'Sustained vacancy — review rent, marketing, channel mix.', count: vac30.length });
    }

    var moveouts = units.filter(function (u) { return u.upcomingMoveOut; });
    if (moveouts.length) {
      insights.push({ severity: 'info', kind: 'upcoming-moveouts',
        title: moveouts.length + ' move-outs in next 30 days',
        detail: 'Begin re-letting workflow — notify ops & marketing.', count: moveouts.length });
    }

    var decliners = stats.filter(function (s) { return s.delta < -0.02; });
    if (decliners.length) {
      insights.push({
        severity: 'warn', kind: 'declining',
        title: decliners.length + ' ' + (decliners.length === 1 ? 'property has' : 'properties have') + ' declining occupancy',
        detail: decliners.slice(0, 3).map(function (s) {
          return s.property.name + ' ' + (s.delta * 100).toFixed(1) + 'pp vs last month';
        }).join(' · '),
        count: decliners.length,
      });
    }

    return insights;
  }

  var _DQ_MAP = {
    'missing_move_in':   { severity: 'warn', label: 'units missing move-in date' },
    'missing_move_out':  { severity: 'warn', label: 'leases missing move-out date' },
    'inverted_dates':    { severity: 'bad',  label: 'leases with inverted dates' },
    'occupied_no_lease': { severity: 'bad',  label: 'occupied units with no active lease' },
    'vacant_with_lease': { severity: 'warn', label: 'units vacant but lease active' },
    'tenant_multi_unit': { severity: 'warn', label: 'tenants assigned to multiple units' },
    'unit_no_tenant':    { severity: 'bad',  label: 'occupied units with no tenant attached' },
  };

  function _buildDataQuality(dqData) {
    if (!dqData || !dqData.issues) return [];
    var tally = {};
    for (var i = 0; i < dqData.issues.length; i++) {
      var t = dqData.issues[i].type;
      tally[t] = (tally[t] || 0) + 1;
    }
    return Object.keys(tally).map(function (t) {
      var count = tally[t];
      var def = _DQ_MAP[t] || { severity: 'warn', label: 'issues of type ' + t };
      return { severity: def.severity, title: count + ' ' + def.label, count: count };
    });
  }

  // ---- Bootstrap -----------------------------------------------------
  window.TAP_DATA_READY = (async function () {
    const month = urlMonth();
    try {
      const apiData = await fetchAllData(month);
      buildTapData(apiData, month);
    } catch (err) {
      console.warn('[TAP] Live API unavailable — falling back to mock data.', err.message);
      _buildMockData(month);
    }
  })();

  // ---- Mock data fallback -------------------------------------------
  // Deterministic seeded data so the dashboard is usable during development
  // even when the CRM/API is unreachable.

  function _buildMockData(month) {
    // Seeded RNG (mulberry32)
    function mulberry32(seed) {
      var s = seed >>> 0;
      return function () {
        s |= 0; s = (s + 0x6D2B79F5) | 0;
        var t = Math.imul(s ^ (s >>> 15), 1 | s);
        t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
        return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
      };
    }
    function pick(rng, arr) { return arr[Math.floor(rng() * arr.length)]; }
    function pad(n, w) { return String(n).padStart(w, '0'); }
    function addDays(d, n) { var o = new Date(d.getTime()); o.setUTCDate(o.getUTCDate() + n); return o; }
    function fmt(d) { return d ? d.toISOString().slice(0, 10) : null; }

    var DAYS = daysInMonthStr(month);
    var TODAY = new Date();
    var TODAY_DAY = TODAY.getDate();
    var MONTH_START = monthStartDate(month);
    var MONTH_END = monthEndDate(month);
    var [yr, mo] = month.split('-').map(Number);
    var PREV_MONTH = prevMonthStr(month);

    var PROPS_CFG = [
      { id: 'P01', name: 'Ember House',        type: 'Co-living',  region: 'North',   units: 28, target: 0.92, baseOcc: 0.94, prevOcc: 0.91 },
      { id: 'P02', name: 'Lattice Court',      type: 'Co-living',  region: 'Central', units: 32, target: 0.90, baseOcc: 0.88, prevOcc: 0.90 },
      { id: 'P03', name: 'Mercer Lofts',       type: 'Serviced',   region: 'Central', units: 18, target: 0.88, baseOcc: 0.82, prevOcc: 0.85 },
      { id: 'P04', name: 'Northshore Studios', type: 'Student',    region: 'North',   units: 24, target: 0.95, baseOcc: 0.97, prevOcc: 0.96 },
      { id: 'P05', name: 'Oak & Pine',         type: 'Co-living',  region: 'East',    units: 20, target: 0.90, baseOcc: 0.91, prevOcc: 0.89 },
      { id: 'P06', name: 'Parkline Yard',      type: 'Co-living',  region: 'South',   units: 16, target: 0.90, baseOcc: 0.74, prevOcc: 0.81 },
      { id: 'P07', name: 'Quartz Heights',     type: 'Serviced',   region: 'West',    units: 14, target: 0.85, baseOcc: 0.86, prevOcc: 0.84 },
      { id: 'P08', name: 'Riverwalk Annex',    type: 'Student',    region: 'East',    units: 22, target: 0.94, baseOcc: 0.93, prevOcc: 0.95 },
    ];

    var FIRST_NAMES = ['Aisha','Maya','Jin','Noah','Priya','Liam','Sofia','Amir','Lena','Owen'];
    var LAST_NAMES  = ['Chen','Patel','Okafor','Schmidt','Garcia','Nakamura','Singh','Murphy','Lin','Brown'];

    var PROPERTIES = PROPS_CFG.map(function (p) {
      return { id: p.id, name: p.name, type: p.type, region: p.region, units: p.units, target: p.target };
    });

    var UNITS = [];
    var unitCounter = 0;
    PROPS_CFG.forEach(function (prop, propIdx) {
      var rng = mulberry32(0xA170 + propIdx * 17);
      var base = prop.baseOcc;
      for (var i = 0; i < prop.units; i++) {
        unitCounter++;
        var floor = Math.floor(i / 8) + 1;
        var unitNum = (i % 8) + 1;
        var label = String.fromCharCode(65 + Math.floor(i / 8)) + '-' + floor + pad(unitNum, 2);
        var kp = rng();
        var kind = prop.type === 'Serviced'
          ? (kp < 0.4 ? 'Studio' : kp < 0.8 ? '1-Bed' : '2-Bed')
          : prop.type === 'Student'
            ? (kp < 0.55 ? 'Shared bed' : 'Private room')
            : (kp < 0.25 ? 'Studio' : kp < 0.75 ? 'Private room' : 'Shared bed');

        var days = new Array(DAYS).fill(false);
        var day = 0;
        var occupied = rng() < base + 0.05;
        while (day < DAYS) {
          if (occupied) {
            var len = Math.min(DAYS - day, 8 + Math.floor(rng() * 24));
            for (var k = 0; k < len; k++) days[day + k] = true;
            day += len;
          } else {
            day += Math.min(DAYS - day, 2 + Math.floor(rng() * 12));
          }
          occupied = !occupied;
        }

        var todayIdx = Math.min(TODAY_DAY - 1, DAYS - 1);
        var isOcc = days[todayIdx];
        var status = isOcc ? 'occupied' : (rng() < 0.25 ? 'reserved' : rng() < 0.35 ? 'maintenance' : 'vacant');

        var tenant = null, leaseStart = null, leaseEnd = null, moveIn = null, moveOut = null;
        var dqFlags = [];
        if (status === 'occupied') {
          tenant = pick(rng, FIRST_NAMES) + ' ' + pick(rng, LAST_NAMES);
          leaseStart = fmt(addDays(TODAY, -30 - Math.floor(rng() * 200)));
          leaseEnd = fmt(addDays(TODAY, 30 + Math.floor(rng() * 180)));
          moveIn = fmt(addDays(new Date(leaseStart + 'T00:00:00Z'), Math.floor(rng() * 5)));
          if (rng() < 0.03) { dqFlags.push('missing-movein'); moveIn = null; }
          if (rng() < 0.02) { dqFlags.push('inverted-lease'); leaseEnd = fmt(addDays(new Date(leaseStart + 'T00:00:00Z'), -10)); }
        } else if (status === 'reserved') {
          tenant = pick(rng, FIRST_NAMES) + ' ' + pick(rng, LAST_NAMES);
          leaseStart = fmt(addDays(TODAY, Math.floor(rng() * 20)));
          leaseEnd = fmt(addDays(TODAY, 180 + Math.floor(rng() * 180)));
          moveIn = leaseStart;
        }

        var daysVacant = 0;
        if (status === 'vacant' || status === 'maintenance') {
          for (var kk = todayIdx; kk >= 0 && !days[kk]; kk--) daysVacant++;
          daysVacant += Math.floor(rng() * 22);
        }

        var upcomingMoveOut = false;
        if (status === 'occupied' && leaseEnd) {
          var diff = Math.round((new Date(leaseEnd + 'T00:00:00Z') - TODAY) / 86400000);
          if (diff > 0 && diff <= 30) upcomingMoveOut = true;
        }

        if (status === 'occupied' && rng() < 0.015) { dqFlags.push('occupied-no-tenant'); tenant = null; }
        if (status === 'vacant' && rng() < 0.02) dqFlags.push('vacant-with-lease');

        var notes = '';
        if (status === 'maintenance') notes = pick(rng, ['AC repair','Repaint scheduled','Plumbing fix','Deep clean','Furniture refresh']);
        else if (status === 'vacant' && daysVacant > 30) notes = 'Long vacancy — listing under review';
        else if (upcomingMoveOut) notes = 'Tenant gave 30-day notice';

        UNITS.push({
          id: prop.id + '-' + pad(unitCounter, 3),
          propertyId: prop.id,
          label: label,
          kind: kind,
          floor: floor,
          days: days,
          status: status,
          tenant: tenant,
          leaseStart: leaseStart,
          leaseEnd: leaseEnd,
          moveIn: moveIn,
          moveOut: moveOut,
          daysVacant: daysVacant,
          upcomingMoveOut: upcomingMoveOut,
          notes: notes,
          dqFlags: dqFlags,
          nextAvailable: status === 'vacant'
            ? fmt(addDays(TODAY, 1 + Math.floor(rng() * 14)))
            : status === 'maintenance'
              ? fmt(addDays(TODAY, 5 + Math.floor(rng() * 21)))
              : null,
          crmLink: null,
        });
      }
    });

    function propStats(prop) {
      var units = UNITS.filter(function (u) { return u.propertyId === prop.id; });
      var cfg = PROPS_CFG.find(function (c) { return c.id === prop.id; });
      var totalUnitDays = units.length * DAYS;
      var occUnitDays = 0;
      units.forEach(function (u) { for (var d = 0; d < DAYS; d++) if (u.days[d]) occUnitDays++; });
      var financeOccCount = units.filter(function (u) { return u.days.some(Boolean); }).length;
      var financeRate = financeOccCount / (units.length || 1);
      var opsRate = occUnitDays / (totalUnitDays || 1);
      var occupied = units.filter(function (u) { return u.status === 'occupied'; }).length;
      var vacant   = units.filter(function (u) { return u.status === 'vacant'; }).length;
      var reserved = units.filter(function (u) { return u.status === 'reserved'; }).length;
      var maintenance = units.filter(function (u) { return u.status === 'maintenance'; }).length;
      var moveIns  = units.filter(function (u) { return u.moveIn && u.moveIn.startsWith(month); }).length;
      var moveOuts = units.filter(function (u) { return u.upcomingMoveOut; }).length;
      var daily = [];
      for (var d = 0; d < DAYS; d++) {
        var occ = units.filter(function (u) { return u.days[d]; }).length;
        daily.push({ day: d + 1, occ: occ, total: units.length, rate: occ / (units.length || 1) });
      }
      return {
        property: prop,
        units: units.length,
        occupied: occupied, vacant: vacant, reserved: reserved, maintenance: maintenance,
        financeOccCount: financeOccCount, financeRate: financeRate,
        opsRate: opsRate, opsRatePrev: cfg.prevOcc,
        delta: opsRate - cfg.prevOcc,
        moveIns: moveIns, moveOuts: moveOuts,
        daily: daily, lastUpdated: 'mock data',
      };
    }

    var PROPERTY_STATS = PROPERTIES.map(propStats);

    var totalUnits = PROPERTY_STATS.reduce(function (a, s) { return a + s.units; }, 0) || 1;
    var dailyAgg = [];
    for (var d = 0; d < DAYS; d++) {
      var occ = 0, tot = 0;
      PROPERTY_STATS.forEach(function (s) { occ += s.daily[d].occ; tot += s.daily[d].total; });
      dailyAgg.push({ day: d + 1, occ: occ, total: tot, rate: occ / (tot || 1) });
    }
    var opsRate = dailyAgg.reduce(function (a, d) { return a + d.rate; }, 0) / DAYS;
    var prevAvg = PROPERTY_STATS.reduce(function (a, s) { return a + s.opsRatePrev * s.units; }, 0) / totalUnits;
    var sortedDays = dailyAgg.slice().sort(function (a, b) { return b.rate - a.rate; });
    var todayIdx = Math.min(TODAY_DAY - 1, DAYS - 1);

    var PORTFOLIO = {
      totalUnits: totalUnits,
      occupied: PROPERTY_STATS.reduce(function (a, s) { return a + s.occupied; }, 0),
      vacant:   PROPERTY_STATS.reduce(function (a, s) { return a + s.vacant; }, 0),
      reserved: PROPERTY_STATS.reduce(function (a, s) { return a + s.reserved; }, 0),
      maintenance: PROPERTY_STATS.reduce(function (a, s) { return a + s.maintenance; }, 0),
      moveIns:  PROPERTY_STATS.reduce(function (a, s) { return a + s.moveIns; }, 0),
      moveOuts: PROPERTY_STATS.reduce(function (a, s) { return a + s.moveOuts; }, 0),
      financeOccCount: PROPERTY_STATS.reduce(function (a, s) { return a + s.financeOccCount; }, 0),
      financeRate: PROPERTY_STATS.reduce(function (a, s) { return a + s.financeOccCount; }, 0) / totalUnits,
      opsRate: opsRate, opsRatePrev: prevAvg, delta: opsRate - prevAvg,
      dailyAgg: dailyAgg,
      highest: sortedDays[0] || { day: 1, rate: 0 },
      lowest:  sortedDays[sortedDays.length - 1] || { day: 1, rate: 0 },
      todayRate: dailyAgg[todayIdx] ? dailyAgg[todayIdx].rate : 0,
      belowTarget: PROPERTY_STATS.filter(function (s) { return s.opsRate < s.property.target; }).length,
    };

    var INSIGHTS = _buildInsights(PROPERTY_STATS, UNITS);

    var missMI  = UNITS.filter(function (u) { return u.dqFlags.includes('missing-movein'); });
    var inverted = UNITS.filter(function (u) { return u.dqFlags.includes('inverted-lease'); });
    var occNoT   = UNITS.filter(function (u) { return u.dqFlags.includes('occupied-no-tenant'); });
    var vacWL    = UNITS.filter(function (u) { return u.dqFlags.includes('vacant-with-lease'); });
    var DATA_QUALITY = [];
    if (missMI.length)  DATA_QUALITY.push({ severity: 'warn', title: missMI.length + ' units missing move-in date',                       count: missMI.length });
    if (inverted.length) DATA_QUALITY.push({ severity: 'bad',  title: inverted.length + ' units with lease end before lease start',        count: inverted.length });
    if (occNoT.length)   DATA_QUALITY.push({ severity: 'bad',  title: occNoT.length + ' occupied units with no tenant attached',           count: occNoT.length });
    if (vacWL.length)    DATA_QUALITY.push({ severity: 'warn', title: vacWL.length + ' units marked vacant but have an active lease',      count: vacWL.length });

    window.TAP_DATA = {
      TODAY: TODAY, MONTH_START: MONTH_START, MONTH_END: MONTH_END,
      DAYS_IN_MONTH: DAYS, TODAY_DAY: TODAY_DAY,
      PROPERTIES: PROPERTIES, UNITS: UNITS, PROPERTY_STATS: PROPERTY_STATS,
      PORTFOLIO: PORTFOLIO, INSIGHTS: INSIGHTS, DATA_QUALITY: DATA_QUALITY,
      helpers: {},
      usingMock: true,
    };
  }
})();
