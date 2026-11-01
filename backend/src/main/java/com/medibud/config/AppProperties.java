package com.medibud.config;

import org.springframework.boot.context.properties.ConfigurationProperties;
import org.springframework.stereotype.Component;

/** Reads app.data-mode from application.yml / DATA_MODE env. */
@Component
@ConfigurationProperties(prefix = "app")
public class AppProperties {

	/** dummy = load seed JSON; real = skip dummy hospitals. */
	private String dataMode = "dummy";

	public String getDataMode() {
		return dataMode;
	}

	public void setDataMode(String dataMode) {
		this.dataMode = dataMode;
	}

	public boolean isDummy() {
		return !"real".equalsIgnoreCase(dataMode);
	}
}
