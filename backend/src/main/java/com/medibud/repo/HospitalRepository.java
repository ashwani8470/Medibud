package com.medibud.repo;

import org.springframework.data.jpa.repository.JpaRepository;

import com.medibud.domain.Hospital;

/** Database access for hospitals. Controllers must not use this directly. */
public interface HospitalRepository extends JpaRepository<Hospital, Long> {

	long countByDemoTrue();
}
