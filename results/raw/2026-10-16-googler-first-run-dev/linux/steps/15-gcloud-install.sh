# Container-only (a gLinux host has gcloud): the Google Cloud CLI by the official Debian/Ubuntu route
# (https://docs.cloud.google.com/sdk/docs/install, "Debian/Ubuntu", newer distributions), as dev with sudo.
# The page's lines verbatim except -y on apt-get install (docker exec has no terminal to answer the prompt).
sudo apt-get update || exit 1
sudo apt-get install -y ca-certificates gnupg curl || exit 1
curl https://packages.cloud.google.com/apt/doc/apt-key.gpg | sudo gpg --dearmor -o /usr/share/keyrings/cloud.google.gpg || exit 1
echo "deb [signed-by=/usr/share/keyrings/cloud.google.gpg] https://packages.cloud.google.com/apt cloud-sdk main" | sudo tee -a /etc/apt/sources.list.d/google-cloud-sdk.list || exit 1
sudo apt-get update && sudo apt-get install -y google-cloud-cli || exit 1
dpkg-query -W google-cloud-cli
gcloud --version
