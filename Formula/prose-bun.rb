class ProseBun < Formula
  desc "Run Prose programs through an installed agent harness"
  homepage "https://prose.md"
  version "0.15.0-rc.3"
  license "MIT"
  on_macos do
    on_arm do
      url "https://pkg.prose.md/cli/releases/0.15.0-rc.3/openprose-prose-cli-bun-0.15.0-rc.3-darwin-arm64.tar.gz"
      sha256 "e7bb95bbf9b67204a72fb927f730c5ec53e6d6aa36fc899d5794bd9bc081e9b4"
    end
    on_intel do
      url "https://pkg.prose.md/cli/releases/0.15.0-rc.3/openprose-prose-cli-bun-0.15.0-rc.3-darwin-x64.tar.gz"
      sha256 "a6c52869faca01f7f3b4024392a61f0d98d5ccffc1fef1c67188bb14aa71bdb6"
    end
  end
  on_linux do
    on_arm do
      url "https://pkg.prose.md/cli/releases/0.15.0-rc.3/openprose-prose-cli-bun-0.15.0-rc.3-linux-arm64-gnu.tar.gz"
      sha256 "5dea2752c4dc1ab967c4e1c7006e5e496788c08ba4a6198cc566a18360ebc5d6"
    end
    on_intel do
      url "https://pkg.prose.md/cli/releases/0.15.0-rc.3/openprose-prose-cli-bun-0.15.0-rc.3-linux-x64-gnu.tar.gz"
      sha256 "67f8e7e3ce2b6d06f5dbb19413616cad6f1e8893532affbbfae9a8256db5c49e"
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
    assert_equal "prose 0.15.0-rc.3 (bun)", shell_output("#{bin}/prose --version").strip
  end
end
