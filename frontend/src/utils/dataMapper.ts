// src/utils/dataMapper.ts

// 1. Frontend (CamelCase) -> Backend (Snake_Case)
export const mapFormToBackend = (formData: any) => {
  return {
    mukkadam_name: formData.mukkadamName,
    mobile_numbers: formData.mobileNumbers,
    village: formData.village,
    has_smartphone: formData.hasSmartphone,
    is_permanent: formData.isPermanent, // NEW
    
    crew_size: formData.crewSize,
    max_crew_capacity: formData.maxCrewCapacity,
    splitting_logic: formData.splittingLogic,
    deputy_mukkadam_name: formData.deputyMukkadamName,
    deputy_mukkadam_mobile: formData.deputyMukkadamMobile,
    
    // Nested Arrays/Objects
    team_members: formData.teamMembers, // Already includes gender
    
    // NEW: Children Details
    number_of_children: formData.numberOfChildren || 0,
    children_caretaker: formData.childrenCaretaker || '',
    
    // NEW: Work History & Location Issues
    work_history: formData.workHistory || [],
    location_issues: formData.locationIssues || [],
    

    current_latitude: formData.currentLatitude || null,
    current_longitude: formData.currentLongitude || null,
    

    start_date: formData.startDate || null,
    end_date: formData.endDate || null,
    daily_work_timing: formData.dailyWorkTiming,
    team_availabilities: formData.teamAvailabilities,
    
    rate_card: formData.rateCard,
    
    home_location: formData.homeLocation,
    preferred_work_locations: formData.preferredWorkLocations,
    max_travel_distance: formData.maxTravelDistance,
    
    transport_mode: formData.transportMode,
    transport_charges: formData.transportCharges,
    transport_arranged_by: formData.transportArrangedBy,
    
    payment_details: formData.paymentDetails,
    
    work_mode: formData.workMode,
    aadhar_number: formData.aadharNumber,
    pan_number: formData.panNumber,
    move_in_preferred_region: formData.moveInPreferredRegion,
    referred_by: formData.referredBy ? parseInt(formData.referredBy) : null,
    referral_source_text: formData.referralSourceText,
    referral_source: formData.referralSource,
    notification_preferences: formData.notificationPreferences,
    other_commitments: formData.otherCommitments,
  };
};

// 2. Backend (Snake_Case) -> Frontend (CamelCase)
export const mapBackendToForm = (apiData: any) => {
  return {
    mukkadamName: apiData.mukkadam_name || '',
    mobileNumbers: apiData.mobile_numbers || '',
    village: apiData.village || '',
    hasSmartphone: apiData.has_smartphone || 'no',
    isPermanent: apiData.is_permanent || false, // NEW
    

    currentLatitude: apiData.current_latitude || '',
    currentLongitude: apiData.current_longitude || '',
    crewSize: apiData.crew_size || '',
    maxCrewCapacity: apiData.max_crew_capacity || '',
    splittingLogic: apiData.splitting_logic || '',
    deputyMukkadamName: apiData.deputy_mukkadam_name || '',
    deputyMukkadamMobile: apiData.deputy_mukkadam_mobile || '',
    
    teamMembers: apiData.team_members || [], // Already includes gender
    
    // NEW: Children Details
    numberOfChildren: apiData.number_of_children || 0,
    childrenCaretaker: apiData.children_caretaker || '',
    
    // NEW: Work History & Location Issues
    workHistory: apiData.work_history || [],
    locationIssues: apiData.location_issues || [],
    
    startDate: apiData.start_date || '',
    endDate: apiData.end_date || '',
    dailyWorkTiming: apiData.daily_work_timing || '',
    teamAvailabilities: apiData.team_availabilities || [],
    
    rateCard: apiData.rate_card || {
      pruning: '',
      pasting: '',
      firstFailFutRemoval: '',
      secondFailFutRemoval: '',
      firstDipping: '',
      secondDipping: '',
      thirdDipping: '',
      shootTyingStrings: '',
      shootTyingClips: '',
      bagalBaliFutRemoval: '',
      bunchThinning: '',
      fingerThinning: '',
      berryThinning: '',
      bunchSelection: '',
      bunchTying: '',
      bunchVariation: '',
      shendaTopping: '',
      paperWrapping: '',
      paperRemoval: '',
      aprilPruning: '',
      harvesting: '',
      newPlantation: '',
      other: '',
    },
    
    homeLocation: apiData.home_location || '',
    preferredWorkLocations: apiData.preferred_work_locations || '',
    maxTravelDistance: apiData.max_travel_distance || '',
    
    transportMode: apiData.transport_mode || '',
    transportCharges: apiData.transport_charges || {
      bikeChargePerBike: '', bikeBeyondKm: '', pickupChargeDetails: '',
      currentlyStationedAt: '', freeFromDate: '',
    },
    transportArrangedBy: apiData.transport_arranged_by || '',
    
    paymentDetails: apiData.payment_details || {
      modes: { cash: false, upi: false, bank: false },
      upiId: '', accountNumber: '', ifscCode: '', bankNameBranch: '',
    },
    
    workMode: apiData.work_mode || '',
    moveInPreferredRegion: apiData.move_in_preferred_region || '',
    
    referralSource: apiData.referral_source || '',
    notificationPreferences: apiData.notification_preferences || {
      whatsapp: false, sms: false, call: false,
    },

    referredBy: apiData.referred_by || '',
    referredByName: apiData.referred_by_name || '',
    referralSourceText: apiData.referral_source_text || '',
    
    referralsList: apiData.referrals_list || [],
    aadharNumber: apiData.aadhar_number || '',
    panNumber: apiData.pan_number || '',
    
    otherCommitments: apiData.other_commitments || '',
  };
};