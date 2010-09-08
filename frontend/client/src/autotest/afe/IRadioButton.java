package autotest.afe;

import com.google.gwt.user.client.ui.HasText;
import com.google.gwt.user.client.ui.HasValue;
import com.google.gwt.user.client.ui.RadioButton;

public interface IRadioButton extends HasValue<Boolean>, HasText {
    public void setEnabled(boolean enabled);

    public static class RadioButtonImpl extends RadioButton implements IRadioButton {
        public RadioButtonImpl(String name) {
            super(name);
        }

        public RadioButtonImpl(String name, String choice) {
            super(name, choice);
        }
    }
}
