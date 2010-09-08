package autotest.afe;

import autotest.afe.IRadioButton.RadioButtonImpl;

import com.google.gwt.user.client.ui.Composite;
import com.google.gwt.user.client.ui.HorizontalPanel;
import com.google.gwt.user.client.ui.Panel;

public class ControlTypeSelectDisplay extends Composite implements ControlTypeSelect.Display {
    public static final String RADIO_GROUP = "controlTypeGroup";

    private RadioButtonImpl client = new RadioButtonImpl(RADIO_GROUP);
    private RadioButtonImpl server = new RadioButtonImpl(RADIO_GROUP);
    private Panel panel = new HorizontalPanel();

    public ControlTypeSelectDisplay() {
        panel.add(client);
        panel.add(server);
        client.setValue(true); // client is default
        initWidget(panel);
    }

    public IRadioButton getClient() {
        return client;
    }

    public IRadioButton getServer() {
        return server;
    }
}
