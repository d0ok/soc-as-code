resource "docker_image" "nginx_test" {
  name = "nginx:latest"
}

resource "docker_container" "nginx_test" {
  name = "tf-test-nginx"
  image = docker_image.nginx_test.image_id
  
  ports {
    internal = 80
    external = 8080
  }
}
