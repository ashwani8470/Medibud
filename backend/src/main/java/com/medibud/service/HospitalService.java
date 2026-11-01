package com.medibud.service;

import java.util.Comparator;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

import org.springframework.http.HttpStatus;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.web.server.ResponseStatusException;

import com.medibud.domain.BedInventory;
import com.medibud.domain.BedType;
import com.medibud.domain.Hospital;
import com.medibud.repo.HospitalRepository;
import com.medibud.web.dto.HospitalDtos.BedCount;
import com.medibud.web.dto.HospitalDtos.DoctorView;
import com.medibud.web.dto.HospitalDtos.HospitalDetail;
import com.medibud.web.dto.HospitalDtos.HospitalSummary;

/**
 * All hospital reads go through here (not through the repository in controllers).
 * Later, DATA_MODE=real can swap this implementation without changing the UI.
 */
@Service
public class HospitalService {

	private final HospitalRepository hospitals;
	private final DistanceService distance;

	public HospitalService(HospitalRepository hospitals, DistanceService distance) {
		this.hospitals = hospitals;
		this.distance = distance;
	}

	@Transactional(readOnly = true)
	public List<HospitalSummary> search(double lat, double lng, boolean emergency) {
		return hospitals.findAll().stream()
				.map(h -> toSummary(h, lat, lng))
				.sorted(Comparator.comparingDouble(HospitalSummary::distanceKm))
				.filter(h -> !emergency || hasEmergencyBed(h))
				.limit(emergency ? 3 : Long.MAX_VALUE)
				.toList();
	}

	@Transactional(readOnly = true)
	public HospitalDetail get(Long id, double lat, double lng) {
		Hospital hospital = hospitals.findById(id)
				.orElseThrow(() -> new ResponseStatusException(HttpStatus.NOT_FOUND, "Hospital not found"));
		return toDetail(hospital, lat, lng);
	}

	private boolean hasEmergencyBed(HospitalSummary h) {
		BedCount general = h.beds().getOrDefault("GENERAL", new BedCount(0, 0));
		BedCount icu = h.beds().getOrDefault("ICU", new BedCount(0, 0));
		return general.free() + icu.free() > 0;
	}

	private HospitalSummary toSummary(Hospital h, double lat, double lng) {
		double km = distance.km(lat, lng, h.getLat(), h.getLng());
		return new HospitalSummary(
				h.getId(),
				h.getName(),
				h.getLat(),
				h.getLng(),
				h.getPhone(),
				h.getAddress(),
				round1(km),
				distance.etaMinutes(km),
				h.getUpdatedAt(),
				h.isDemo(),
				bedMap(h));
	}

	private HospitalDetail toDetail(Hospital h, double lat, double lng) {
		double km = distance.km(lat, lng, h.getLat(), h.getLng());
		List<String> departments = h.getDoctors().stream()
				.map(d -> d.getSpecialty())
				.distinct()
				.toList();
		List<DoctorView> doctors = h.getDoctors().stream()
				.map(d -> new DoctorView(
						d.getId(),
						d.getName(),
						d.getSpecialty(),
						d.getStatus().name(),
						d.getNextFreeSlot()))
				.toList();
		return new HospitalDetail(
				h.getId(),
				h.getName(),
				h.getLat(),
				h.getLng(),
				h.getPhone(),
				h.getAddress(),
				round1(km),
				distance.etaMinutes(km),
				h.getUpdatedAt(),
				h.isDemo(),
				h.getFacilities(),
				departments,
				bedMap(h),
				doctors);
	}

	private Map<String, BedCount> bedMap(Hospital h) {
		Map<String, BedCount> map = new LinkedHashMap<>();
		for (BedType type : BedType.values()) {
			map.put(type.name(), new BedCount(0, 0));
		}
		for (BedInventory b : h.getBeds()) {
			map.put(b.getBedType().name(), new BedCount(b.getFree(), b.getTotal()));
		}
		return map;
	}

	private static double round1(double km) {
		return Math.round(km * 10.0) / 10.0;
	}
}
