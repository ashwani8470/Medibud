package com.medibud.repo;

import java.util.Optional;

import org.springframework.data.jpa.repository.JpaRepository;

import com.medibud.domain.AppUser;

public interface UserRepository extends JpaRepository<AppUser, Long> {

	Optional<AppUser> findByEmailIgnoreCase(String email);
}
