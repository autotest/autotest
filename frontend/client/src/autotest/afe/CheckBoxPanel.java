package autotest.afe;

import java.util.ArrayList;
import java.util.List;

public class CheckBoxPanel {
    public static interface Display {
        public ICheckBox generateCheckBox(int index);
    }

    private List<ICheckBox> checkBoxes = new ArrayList<ICheckBox>();
    private Display display;

    public void bindDisplay(Display display) {
        this.display = display;
    }

    public ICheckBox generateCheckBox() {
        return display.generateCheckBox(checkBoxes.size());
    }

    public void add(ICheckBox checkBox) {
        checkBoxes.add(checkBox);
    }

    public List<ICheckBox> getChecked() {
        List<ICheckBox> result = new ArrayList<ICheckBox>();
        for(ICheckBox checkBox : checkBoxes) {
            if (checkBox.getValue()) {
                result.add(checkBox);
            }
        }
        return result;
    }

    public void setEnabled(boolean enabled) {
        for(ICheckBox thisBox : checkBoxes) {
            thisBox.setEnabled(enabled);
        }
    }

    public void reset() {
        for (ICheckBox thisBox : checkBoxes) {
            thisBox.setValue(false);
        }
    }
}
