package com.medibud.web;

import java.util.List;

import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

import com.medibud.service.HospitalService;
import com.medibud.web.dto.HospitalDtos.HospitalDetail;
import com.medibud.web.dto.HospitalDtos.HospitalSummary;

/**
 * Patient search API. Default lat/lng = Civil Lines, Kanpur
 * (same as the HTML demo dropdown).
 */
@RestController
@RequestMapping("/api/hospitals")
public class HospitalController {

	private final HospitalService hospitalService;

	public HospitalController(HospitalService hospitalService) {
		this.hospitalService = hospitalService;
	}

	@GetMapping
	public List<HospitalSummary> list(
			@RequestParam(defaultValue = "26.467") double lat,
			@RequestParam(defaultValue = "80.35") double lng,
			@RequestParam(defaultValue = "false") boolean emergency) {
		return hospitalService.search(lat, lng, emergency);
	}

	@GetMapping("/{id}")
	public HospitalDetail one(
			@PathVariable Long id,
			@RequestParam(defaultValue = "26.467") double lat,
			@RequestParam(defaultValue = "80.35") double lng) {
		return hospitalService.get(id, lat, lng);
	}
}
