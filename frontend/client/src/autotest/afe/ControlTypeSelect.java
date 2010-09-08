package autotest.afe;

public class ControlTypeSelect {
    public static interface Display {
        public IRadioButton getClient();
        public IRadioButton getServer();
    }

    private Display display;

    public void bindDisplay(Display display) {
        this.display = display;
        display.getClient().setText(TestSelector.CLIENT_TYPE);
        display.getServer().setText(TestSelector.SERVER_TYPE);
    }

    public String getControlType() {
        if (display.getClient().getValue()) {
            return display.getClient().getText();
        }
        return display.getServer().getText();
    }

    public void setControlType(String type) {
        if (display.getClient().getText().equals(type)) {
            display.getClient().setValue(true);
        } else if (display.getServer().getText().equals(type)) {
            display.getServer().setValue(true);
        } else {
            throw new IllegalArgumentException("Invalid control type");
        }
    }

    public void setEnabled(boolean enabled) {
        display.getClient().setEnabled(enabled);
        display.getServer().setEnabled(enabled);
    }
}
