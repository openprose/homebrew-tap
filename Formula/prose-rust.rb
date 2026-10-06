class ProseRust < Formula
  desc "Run Prose programs through an installed agent harness"
  homepage "https://prose.md"
  version "0.15.0-rc.2"
  license "MIT"
  on_macos do
    on_arm do
      url "https://pkg.prose.md/cli/releases/0.15.0-rc.2/openprose-prose-cli-rust-0.15.0-rc.2-darwin-arm64.tar.gz"
      sha256 "9182bc65dac541aa9f0bb92500ca90274c3d36daf69b0ac0b8249adfef1f61d0"
    end
    on_intel do
      url "https://pkg.prose.md/cli/releases/0.15.0-rc.2/openprose-prose-cli-rust-0.15.0-rc.2-darwin-x64.tar.gz"
      sha256 "d9fd0db4f90f4a6abe9b36661c8be2166b821ba5167c9bc09845d85df67acf08"
    end
  end
  on_linux do
    on_arm do
      url "https://pkg.prose.md/cli/releases/0.15.0-rc.2/openprose-prose-cli-rust-0.15.0-rc.2-linux-arm64-gnu.tar.gz"
      sha256 "0ddfb835cc4debcd7c5c4e1db7cd4d7835a7682ec39e676c7174fdf76fccb954"
    end
    on_intel do
      url "https://pkg.prose.md/cli/releases/0.15.0-rc.2/openprose-prose-cli-rust-0.15.0-rc.2-linux-x64-gnu.tar.gz"
      sha256 "c0e1da4a25ab402b64358bfe8d95ed646bf7fd4883b8699a6e3e5e3a41402609"
    end
  end

  def install
    bin.install "prose" => "prose"
  end

  def caveats
    <<~EOS
      Install and authenticate a supported agent harness separately.
      Linux requires glibc 2.34 or newer.
      This is an experimental prerelease.
      macOS binaries are not Developer ID signed or notarized.
    EOS
  end

  test do
    assert_equal "prose 0.15.0-rc.2 (rust)", shell_output("#{bin}/prose --version").strip
  end
end
