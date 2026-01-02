// Availability Management Module
function searchMukkadam() {
    const query = document.getElementById('availSearchInput').value.trim().toLowerCase();
    const resultsDiv = document.getElementById('searchResults');
    
    if (!query) {
        resultsDiv.classList.add('hidden');
        return;
    }

    const isMobile = /^\d+$/.test(query);
    let matches = [];
    
    if (isMobile) {
        matches = allMukkadams.filter(m => m.mobile.includes(query));
    } else {
        matches = allMukkadams.filter(m => m.name.toLowerCase().includes(query));
    }

    if (matches.length === 0) {
        resultsDiv.innerHTML = `
            <div class="bg-red-50 border border-red-200 rounded-lg p-4">
                <p class="text-red-700 font-semibold">❌ No mukkadam found</p>
            </div>
        `;
        resultsDiv.classList.remove('hidden');
    } else if (matches.length === 1) {
        selectMukkadam(matches[0]);
        resultsDiv.classList.add('hidden');
    } else {
        showDisambiguation(matches, 'village');
    }
}

function showDisambiguation(matches, step) {
    const resultsDiv = document.getElementById('searchResults');
    
    if (step === 'village') {
        const byVillage = {};
        matches.forEach(m => {
            if (!byVillage[m.village]) byVillage[m.village] = [];
            byVillage[m.village].push(m);
        });

        if (Object.keys(byVillage).length === 1) {
            showDisambiguation(matches, 'crewSize');
            return;
        }

        resultsDiv.innerHTML = `
            <div class="bg-yellow-50 border border-yellow-200 rounded-lg p-4">
                <p class="font-semibold text-gray-800 mb-3">🔍 Multiple matches found. Select Village:</p>
                <div class="space-y-2">
                    ${Object.entries(byVillage).map(([village, items]) => `
                        <button onclick='disambiguateByVillage(${JSON.stringify(items)})' class="w-full text-left px-4 py-2 bg-white border border-gray-300 rounded hover:bg-blue-50 hover:border-blue-300">
                            📍 ${village} <span class="text-gray-500">(${items.length} mukkadam${items.length > 1 ? 's' : ''})</span>
                        </button>
                    `).join('')}
                </div>
            </div>
        `;
        resultsDiv.classList.remove('hidden');
    } else if (step === 'crewSize') {
        const byCrewSize = {};
        matches.forEach(m => {
            if (!byCrewSize[m.crewSize]) byCrewSize[m.crewSize] = [];
            byCrewSize[m.crewSize].push(m);
        });

        if (Object.keys(byCrewSize).length === 1) {
            showDisambiguation(matches, 'mobile');
            return;
        }

        resultsDiv.innerHTML = `
            <div class="bg-yellow-50 border border-yellow-200 rounded-lg p-4">
                <p class="font-semibold text-gray-800 mb-3">🔍 Still multiple matches. Select Crew Size:</p>
                <div class="space-y-2">
                    ${Object.entries(byCrewSize).sort((a, b) => a[0] - b[0]).map(([size, items]) => `
                        <button onclick='disambiguateByCrewSize(${JSON.stringify(items)})' class="w-full text-left px-4 py-2 bg-white border border-gray-300 rounded hover:bg-blue-50 hover:border-blue-300">
                            👷 ${size} workers <span class="text-gray-500">(${items.length} mukkadam${items.length > 1 ? 's' : ''})</span>
                        </button>
                    `).join('')}
                </div>
            </div>
        `;
        resultsDiv.classList.remove('hidden');
    } else if (step === 'mobile') {
        resultsDiv.innerHTML = `
            <div class="bg-yellow-50 border border-yellow-200 rounded-lg p-4">
                <p class="font-semibold text-gray-800 mb-3">🔍 Select by Mobile Number:</p>
                <div class="space-y-2">
                    ${matches.map(m => `
                        <button onclick='selectMukkadamById(${m.id})' class="w-full text-left px-4 py-2 bg-white border border-gray-300 rounded hover:bg-blue-50 hover:border-blue-300">
                            <div class="font-semibold">${m.name}</div>
                            <div class="text-xs text-gray-600">📍 ${m.village} | 👷 ${m.crewSize} workers | 📱 ${m.mobile}</div>
                        </button>
                    `).join('')}
                </div>
            </div>
        `;
        resultsDiv.classList.remove('hidden');
    }
}

function disambiguateByVillage(matches) {
    showDisambiguation(matches, 'crewSize');
}

function disambiguateByCrewSize(matches) {
    showDisambiguation(matches, 'mobile');
}

function selectMukkadamById(id) {
    const mukkadam = allMukkadams.find(m => m.id === id);
    selectMukkadam(mukkadam);
}

function selectMukkadam(mukkadam) {
    selectedMukkadam = mukkadam;
    
    document.getElementById('selectedMukkadamInfo').innerHTML = `
        <div class="flex items-center justify-between">
            <div>
                <p class="font-bold text-lg">${mukkadam.name}</p>
                <p class="text-gray-600">📱 ${mukkadam.mobile}</p>
                <p class="text-gray-600">📍 ${mukkadam.village} | 👷 ${mukkadam.crewSize} workers</p>
            </div>
            <button onclick="clearSelection()" class="px-3 py-1 bg-red-100 text-red-700 rounded hover:bg-red-200 text-xs font-semibold">
                Clear
            </button>
        </div>
    `;
    
    document.getElementById('selectedMukkadamSection').classList.remove('hidden');
    renderCurrentAvailabilities();
}

function clearSelection() {
    selectedMukkadam = null;
    document.getElementById('selectedMukkadamSection').classList.add('hidden');
    document.getElementById('availSearchInput').value = '';
    document.getElementById('searchResults').classList.add('hidden');
    hideAvailabilityEditor();
}

function renderCurrentAvailabilities() {
    const availabilities = mukkadamAvailabilities[selectedMukkadam?.id] || [];
    const container = document.getElementById('currentAvailabilities');
    
    if (!selectedMukkadam || availabilities.length === 0) {
        container.innerHTML = `
            <p class="text-gray-500 text-sm">No availabilities set yet.</p>
        `;
        hideAvailabilityEditor();
        return;
    }

    container.innerHTML = availabilities.map((avail, index) => {
        const meta = availabilityStatusMeta[avail.status] || availabilityStatusMeta.available;
        
        return `
            <div class="border-2 rounded-lg p-3 ${meta.cardClasses}">
                <div class="flex items-start justify-between gap-3">
                    <div class="flex-1">
                        <p class="font-semibold">${meta.icon} ${meta.label.toUpperCase()}</p>
                        <p class="text-sm mt-1">📅 ${avail.from} to ${avail.to}</p>
                        ${avail.notes ? `<p class="text-xs mt-1">📝 ${avail.notes}</p>` : ''}
                    </div>
                    <div class="flex flex-col gap-2">
                        <button onclick="startEditingAvailability(${index})" class="px-2 py-1 bg-white text-gray-700 rounded hover:bg-gray-100 text-xs font-semibold shadow-sm">
                            ✏️ Update
                        </button>
                        <button onclick="deleteAvailability(${index})" class="px-2 py-1 bg-red-500 text-white rounded hover:bg-red-600 text-xs font-semibold">
                            Delete
                        </button>
                    </div>
                </div>
            </div>
        `;
    }).join('');
}

function startEditingAvailability(index) {
    if (!selectedMukkadam) return;
    const availabilities = mukkadamAvailabilities[selectedMukkadam.id] || [];
    const slot = availabilities[index];
    if (!slot) return;
    editingAvailabilityIndex = index;
    editingAvailabilityOriginal = { ...slot };

    const panel = document.getElementById('availabilityEditorPanel');
    if (panel) panel.classList.remove('hidden');
    document.getElementById('editAvailFrom').value = slot.from;
    document.getElementById('editAvailTo').value = slot.to;
    document.getElementById('editAvailStatus').value = slot.status;
    document.getElementById('editAvailNotes').value = slot.notes || '';
    document.getElementById('editingRangeLabel').textContent = `Editing ${slot.from} → ${slot.to} (${availabilityStatusMeta[slot.status]?.label || 'Slot'})`;
    setAvailabilityEditorDisabled(false);
}

function saveAvailabilityEdit() {
    if (editingAvailabilityIndex === null || !selectedMukkadam) return;
    const newFrom = document.getElementById('editAvailFrom').value;
    const newTo = document.getElementById('editAvailTo').value;
    const status = document.getElementById('editAvailStatus').value;
    const notes = document.getElementById('editAvailNotes').value;

    if (!newFrom || !newTo) {
        alert('Please pick both From and To dates.');
        return;
    }
    if (new Date(newFrom) > new Date(newTo)) {
        alert('From date must be before To date.');
        return;
    }

    const original = editingAvailabilityOriginal;
    if (new Date(newFrom) < new Date(original.from) || new Date(newTo) > new Date(original.to)) {
        alert('New range must stay inside the original slot. Use "Add Availability" for brand new windows.');
        return;
    }

    const availabilities = mukkadamAvailabilities[selectedMukkadam.id];
    const updatedBlocks = [];

    if (compareDates(newFrom, original.from) > 0) {
        updatedBlocks.push({
            from: original.from,
            to: addDays(newFrom, -1),
            status: original.status,
            notes: original.notes
        });
    }

    updatedBlocks.push({
        from: newFrom,
        to: newTo,
        status,
        notes
    });

    if (compareDates(newTo, original.to) < 0) {
        updatedBlocks.push({
            from: addDays(newTo, 1),
            to: original.to,
            status: original.status,
            notes: original.notes
        });
    }

    availabilities.splice(editingAvailabilityIndex, 1, ...updatedBlocks);
    editingAvailabilityIndex = null;
    editingAvailabilityOriginal = null;
    renderCurrentAvailabilities();
    hideAvailabilityEditor();
    alert('✅ Availability updated successfully!');
}

function cancelAvailabilityEdit() {
    hideAvailabilityEditor();
}

function hideAvailabilityEditor() {
    const panel = document.getElementById('availabilityEditorPanel');
    if (panel) panel.classList.add('hidden');
    const label = document.getElementById('editingRangeLabel');
    if (label) label.textContent = 'Select a block above to edit or split it.';
    setAvailabilityEditorDisabled(true);
    editingAvailabilityIndex = null;
    editingAvailabilityOriginal = null;
}

function setAvailabilityEditorDisabled(state) {
    ['editAvailFrom', 'editAvailTo', 'editAvailStatus', 'editAvailNotes', 'saveEditBtn'].forEach(id => {
        const el = document.getElementById(id);
        if (el) el.disabled = state;
    });
}

function addDays(dateStr, days) {
    const date = new Date(dateStr);
    date.setDate(date.getDate() + days);
    return date.toISOString().split('T')[0];
}

function compareDates(a, b) {
    return new Date(a) - new Date(b);
}

function addAvailability() {
    if (!selectedMukkadam) return;

    const from = document.getElementById('newAvailFrom').value;
    const to = document.getElementById('newAvailTo').value;
    const status = document.getElementById('newAvailStatus').value;
    const notes = document.getElementById('newAvailNotes').value;

    if (!from || !to) {
        alert('Please select both From and To dates');
        return;
    }

    if (new Date(from) > new Date(to)) {
        alert('From date must be before To date');
        return;
    }

    if (!mukkadamAvailabilities[selectedMukkadam.id]) {
        mukkadamAvailabilities[selectedMukkadam.id] = [];
    }

    mukkadamAvailabilities[selectedMukkadam.id].push({
        from,
        to,
        status,
        notes
    });

    renderCurrentAvailabilities();
    clearAvailabilityForm();
    alert('✅ Availability added successfully!');
}

function deleteAvailability(index) {
    if (!selectedMukkadam) return;
    
    if (confirm('Are you sure you want to delete this availability?')) {
        mukkadamAvailabilities[selectedMukkadam.id].splice(index, 1);
        renderCurrentAvailabilities();
        if (editingAvailabilityIndex === index) {
            hideAvailabilityEditor();
        }
    }
}

function clearAvailabilityForm() {
    document.getElementById('newAvailFrom').value = '';
    document.getElementById('newAvailTo').value = '';
    document.getElementById('newAvailStatus').value = 'available';
    document.getElementById('newAvailNotes').value = '';
}

function renderProfileStory() {
    const joinedOn = document.getElementById('joinedOnField');
    const joinedThrough = document.getElementById('joinedThroughField');
    const referredBy = document.getElementById('referredByField');
    const recruiter = document.getElementById('recruiterField');
    const firstAssignment = document.getElementById('firstAssignmentField');

    if (!joinedOn) return;
    joinedOn.textContent = formatDisplayDate(profileStory.joinedOn);
    joinedThrough.textContent = profileStory.joinedThrough;
    referredBy.textContent = profileStory.referredBy;
    recruiter.textContent = profileStory.recruiter;
    firstAssignment.textContent = profileStory.firstAssignment;
}

function renderProfileAvailabilityTimeline() {
    const container = document.getElementById('profileAvailabilityTimeline');
    if (!container) return;
    const entries = (mukkadamAvailabilities[highlightedProfileId] || []).slice(0, 4);

    if (entries.length === 0) {
        container.innerHTML = '<p class="text-sm text-gray-500">No availability data yet.</p>';
        return;
    }

    container.innerHTML = entries.map(entry => {
        const meta = availabilityStatusMeta[entry.status] || availabilityStatusMeta.available;
        return `
            <div class="p-3 border-l-4 ${meta.timelineBorder} bg-gray-50 rounded">
                <p class="font-semibold text-sm text-gray-800">${meta.icon} ${meta.label}</p>
                <p class="text-xs text-gray-600">📅 ${formatDisplayDate(entry.from)} - ${formatDisplayDate(entry.to)}</p>
                ${entry.notes ? `<p class="text-xs text-gray-500 mt-1">📝 ${entry.notes}</p>` : ''}
            </div>
        `;
    }).join('');
}

function refreshProfileAvailability() {
    renderProfileAvailabilityTimeline();
}

function formatDisplayDate(dateStr) {
    if (!dateStr) return '--';
    const date = new Date(dateStr);
    if (isNaN(date.getTime())) return dateStr;
    return date.toLocaleDateString('en-IN', { day: '2-digit', month: 'short', year: 'numeric' });
}

// Initialize profile helpers once this module loads
renderProfileStory();
renderProfileAvailabilityTimeline();

