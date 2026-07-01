# Firewall rules for Factorio server

# Allow Factorio game traffic (UDP)
resource "google_compute_firewall" "factorio_game" {
  name    = "factorio-game"
  network = "default"

  allow {
    protocol = "udp"
    ports    = ["34197"]
  }

  source_ranges = ["0.0.0.0/0"]
  target_tags   = ["factorio"]

  description = "Allow Factorio game traffic on UDP port 34197"
}

# Allow Factorio RCON/TCP traffic
resource "google_compute_firewall" "factorio_rcon" {
  name    = "factorio-rcon"
  network = "default"

  allow {
    protocol = "tcp"
    ports    = ["27015"]
  }

  source_ranges = ["0.0.0.0/0"]
  target_tags   = ["factorio"]

  description = "Allow Factorio RCON traffic on TCP port 27015"
}

# Allow SSH for instances with ssh tag
resource "google_compute_firewall" "ssh" {
  name    = "allow-ssh"
  network = "default"

  allow {
    protocol = "tcp"
    ports    = ["22"]
  }

  source_ranges = ["0.0.0.0/0"]
  target_tags   = ["ssh"]

  description = "Allow SSH access"
}
