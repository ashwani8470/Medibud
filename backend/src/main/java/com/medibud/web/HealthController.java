package com.medibud.web;

import java.util.Map;

import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RestController;

import com.medibud.config.AppProperties;

/** Quick check that the backend is up before a demo. */
@RestController
public class HealthController {

	private final AppProperties props;

	public HealthController(AppProperties props) {
		this.props = props;
	}

	@GetMapping("/api/health")
	public Map<String, String> health() {
		return Map.of("status", "ok", "dataMode", props.getDataMode());
	}
}
